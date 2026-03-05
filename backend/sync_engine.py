"""
Odoo -> PostgreSQL Sync Engine.
Handles incremental sync for masters (GLOBAL) and POS (per company).
Uses batch upserts for performance.
"""
import os
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
import time
from odoo_client import OdooClient

logger = logging.getLogger(__name__)

MASTER_JOBS = ['RES_COMPANY', 'RES_USERS', 'RES_PARTNER', 'PRODUCTS', 'ATTRIBUTES', 'STOCK_LOCATIONS', 'STOCK_QUANTS']
POS_JOBS = ['POS_ORDERS']
MULTI_JOBS = ['AR_CREDIT_INVOICES']
ADVISORY_LOCK_ID = 777777


def xid(val):
    """Extract integer id from Odoo many2one field ([id,name] or int or False)."""
    if val is False or val is None:
        return None
    if isinstance(val, (list, tuple)) and len(val) >= 1:
        return val[0]
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    return None


def xdt(val):
    """Parse Odoo date string to Python datetime or None."""
    if not val or val is False:
        return None
    if isinstance(val, str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def xtxt(val):
    """Extract text, treating Odoo False as None."""
    if val is False or val is None:
        return None
    return str(val)


def xm2o_name(val):
    """Extract display name from many2one field [id, 'name'] or False."""
    if val is False or val is None:
        return None
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return str(val[1])
    if isinstance(val, str):
        return val
    return None


def xnum(val):
    """Extract numeric value."""
    if val is False or val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def xbool(val):
    """Extract boolean, but return None if val is literally False (unset)."""
    if val is None:
        return None
    if val is False:
        return False
    return bool(val)


def xbool_nullable(val):
    """For optional boolean fields: None if not set."""
    if val is False or val is None:
        return None
    return bool(val)


class SyncService:
    def __init__(self):
        self.pg_url = os.environ['PG_URL']
        self.odoo_url = os.environ['ODOO_URL']
        self.odoo_db = os.environ['ODOO_DB']
        self.client = OdooClient(self.odoo_url)
        self.credentials = {
            'Ambission': {
                'login': os.environ['ODOO_AMBISSION_LOGIN'],
                'password': os.environ['ODOO_AMBISSION_PASSWORD'],
            },
            'ProyectoModa': {
                'login': os.environ['ODOO_PROYECTOMODA_LOGIN'],
                'password': os.environ['ODOO_PROYECTOMODA_PASSWORD'],
            },
        }
        self._uid_cache = {}
        self._ctx_cache = {}

    def _conn(self):
        return psycopg2.connect(self.pg_url)

    def _auth(self, ck):
        if ck in self._uid_cache:
            return self._uid_cache[ck]
        creds = self.credentials.get(ck, self.credentials['Ambission'])
        uid = self.client.authenticate(self.odoo_db, creds['login'], creds['password'])
        self._uid_cache[ck] = (uid, creds['password'])
        return uid, creds['password']

    def _company_ctx(self, ck):
        if ck in self._ctx_cache:
            return self._ctx_cache[ck]
        uid, pw = self._auth(ck)
        try:
            udata = self.client.read(self.odoo_db, uid, pw, 'res.users', [uid], ['company_id', 'company_ids'])
            if udata:
                cid = xid(udata[0].get('company_id'))
                cids = udata[0].get('company_ids', []) or ([cid] if cid else [])
                ctx = {'allowed_company_ids': cids, 'company_id': cid}
                self._ctx_cache[ck] = (ctx, cid)
                return ctx, cid
        except Exception as e:
            logger.warning(f"Company context for {ck}: {e}")
        self._ctx_cache[ck] = ({}, None)
        return {}, None

    def _paginate(self, uid, pw, model, domain, fields, chunk, ctx=None):
        """ID-based pagination (stable, no duplicates)."""
        all_recs = []
        last_id = 0
        while True:
            page_domain = domain + [('id', '>', last_id)]
            batch = self.client.search_read(self.odoo_db, uid, pw, model, page_domain, fields,
                                            limit=chunk, offset=0, order='id asc', context=ctx)
            if not batch:
                break
            all_recs.extend(batch)
            last_id = max(r['id'] for r in batch)
            if len(batch) < chunk:
                break
        logger.info(f"  Fetched {len(all_recs)} from {model}")
        return all_recs

    def _inc_domain(self, base, cursor, mode):
        d = list(base)
        if mode == 'INCREMENTAL' and cursor:
            d.append(('write_date', '>', cursor.strftime('%Y-%m-%d %H:%M:%S')))
        return d

    # ---- DB helpers (use dedicated short connections for metadata) ----

    def _insert_log(self, job_code, company_key):
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO odoo.sync_run_log (job_code,company_key,started_at,status)
                               VALUES (%s,%s,now(),'RUNNING') RETURNING id""", (job_code, company_key))
                return cur.fetchone()[0]
        finally:
            conn.close()

    def _finish_log(self, log_id, status, rows=0, error=None):
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE odoo.sync_run_log SET ended_at=now(), status=%s,
                               rows_upserted=%s, error_message=%s WHERE id=%s""",
                            (status, rows, error[:500] if error else None, log_id))
        finally:
            conn.close()

    def _update_cursor(self, job_code, cursor, ok=True, error=None):
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                if ok:
                    cur.execute("""UPDATE odoo.sync_job SET last_run_at=now(), last_success_at=now(),
                                   last_cursor=%s, last_error=NULL WHERE job_code=%s""", (cursor, job_code))
                else:
                    cur.execute("""UPDATE odoo.sync_job SET last_run_at=now(), last_error=%s
                                   WHERE job_code=%s""", (str(error)[:500] if error else None, job_code))
        finally:
            conn.close()

    def _get_cursor(self, job_code):
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT last_cursor FROM odoo.sync_job WHERE job_code=%s", (job_code,))
                r = cur.fetchone()
                return r[0] if r else None
        finally:
            conn.close()

    def _batch_upsert(self, sql_template, values, page_size=500):
        """Batch upsert using execute_values for performance."""
        if not values:
            return 0
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                execute_values(cur, sql_template, values, page_size=page_size)
            conn.commit()
            return len(values)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- Main entry ----

    def run_sync(self, job_code=None, mode=None, target='ALL', company_key=None):
        conn = self._conn()
        conn.autocommit = True
        results = []
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
                if not cur.fetchone()[0]:
                    conn.close()
                    return {"success": False, "message": "Otra sincronización en curso.", "results": []}

            with conn.cursor() as cur:
                if job_code:
                    cur.execute("SELECT job_code,mode,chunk_size FROM odoo.sync_job WHERE job_code=%s AND enabled=true ORDER BY priority", (job_code,))
                else:
                    cur.execute("SELECT job_code,mode,chunk_size FROM odoo.sync_job WHERE enabled=true ORDER BY priority")
                jobs = cur.fetchall()

            for jc, jm, cs in jobs:
                em = mode or jm
                is_m = jc in MASTER_JOBS
                is_p = jc in POS_JOBS
                is_multi = jc in MULTI_JOBS
                if target == 'GLOBAL_ONLY' and not is_m:
                    continue
                if target == 'POS_ONLY' and not is_p:
                    continue
                if is_m:
                    results.append(self._run_job(jc, 'GLOBAL', em, cs))
                elif is_p or is_multi:
                    if company_key:
                        results.append(self._run_job(jc, company_key, em, cs))
                    else:
                        for ck in ['Ambission', 'ProyectoModa']:
                            results.append(self._run_job(jc, ck, em, cs))

            return {"success": True, "message": f"Sync: {len(results)} ejecuciones", "results": results}
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            return {"success": False, "message": str(e), "results": results}
        finally:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,))
            except Exception:
                pass
            conn.close()

    def _run_job(self, jc, ck, mode, cs):
        log_id = self._insert_log(jc, ck)
        logger.info(f"Sync start: {jc}/{ck}/{mode}")
        try:
            cursor = self._get_cursor(jc) if mode == 'INCREMENTAL' else None
            handlers = {
                'RES_COMPANY': self._sync_res_company,
                'RES_USERS': self._sync_res_users,
                'RES_PARTNER': self._sync_res_partner,
                'PRODUCTS': self._sync_products,
                'ATTRIBUTES': self._sync_attributes,
                'STOCK_LOCATIONS': self._sync_stock_locations,
                'STOCK_QUANTS': self._sync_stock_quants,
                'POS_ORDERS': self._sync_pos_orders,
                'AR_CREDIT_INVOICES': self._sync_credit_invoices,
            }
            h = handlers[jc]
            if jc in POS_JOBS or jc in MULTI_JOBS:
                rows, new_cursor = h(ck, mode, cursor, cs)
            else:
                rows, new_cursor = h(mode, cursor, cs)
            self._finish_log(log_id, 'OK', rows=rows)
            self._update_cursor(jc, new_cursor or cursor, ok=True)
            logger.info(f"Sync OK: {jc}/{ck} -> {rows} rows")
            return {"job_code": jc, "company_key": ck, "status": "OK", "rows": rows}
        except Exception as e:
            logger.error(f"Sync ERROR: {jc}/{ck}: {e}", exc_info=True)
            self._finish_log(log_id, 'ERROR', error=str(e))
            self._update_cursor(jc, None, ok=False, error=e)
            return {"job_code": jc, "company_key": ck, "status": "ERROR", "error": str(e)[:200]}

    # ---- Track max write_date ----
    def _max_wd(self, recs, prev):
        m = prev
        for r in recs:
            wd = xdt(r.get('write_date'))
            if wd and (m is None or wd > m):
                m = wd
        return m

    # ================================================================
    # MASTERS
    # ================================================================

    def _sync_res_company(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        recs = self._paginate(uid, pw, 'res.company', domain,
                              ['id','name','active','create_date','create_uid','write_date','write_uid'], cs)
        vals = [(r['id'], xtxt(r.get('name')), xbool(r.get('active')),
                 xdt(r.get('write_date')), xdt(r.get('create_date')),
                 xid(r.get('create_uid')), xid(r.get('write_uid'))) for r in recs]
        sql = """INSERT INTO odoo.res_company (company_key,odoo_id,name,active,odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,active=EXCLUDED.active,odoo_write_date=EXCLUDED.odoo_write_date,
                 odoo_create_date=EXCLUDED.odoo_create_date,odoo_create_uid=EXCLUDED.odoo_create_uid,
                 odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_stock_locations(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        fields = ['id', 'name', 'x_nombre', 'complete_name', 'usage', 'active',
                  'location_id', 'company_id', 'create_date', 'create_uid', 'write_date', 'write_uid']
        recs = self._paginate(uid, pw, 'stock.location', domain, fields, cs)
        vals = [
            (r['id'], xtxt(r.get('name')), xtxt(r.get('x_nombre')), xtxt(r.get('complete_name')),
             xtxt(r.get('usage')), xbool(r.get('active')),
             xid(r.get('location_id')), xid(r.get('company_id')),
             xdt(r.get('create_date')), xid(r.get('create_uid')),
             xdt(r.get('write_date')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.stock_location (company_key,odoo_id,name,x_nombre,complete_name,usage,active,
                 location_id,company_id,odoo_create_date,odoo_create_uid,odoo_write_date,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,x_nombre=EXCLUDED.x_nombre,complete_name=EXCLUDED.complete_name,
                 usage=EXCLUDED.usage,active=EXCLUDED.active,location_id=EXCLUDED.location_id,
                 company_id=EXCLUDED.company_id,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_date=EXCLUDED.odoo_write_date,
                 odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_stock_quants(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)

        # Detect the correct qty field name: try 'qty' first (Odoo 10), then 'quantity' (Odoo 12+)
        qty_field = 'qty'
        has_reserved = False
        try:
            test = self.client.search_read(self.odoo_db, uid, pw, 'stock.quant',
                                           [], ['id', 'qty', 'quantity'], limit=5)
            if test:
                # Check which field has actual non-False data
                has_qty_data = any(r.get('qty') not in (False, None) for r in test)
                has_quantity_data = any(r.get('quantity') not in (False, None) for r in test)
                if has_qty_data:
                    qty_field = 'qty'
                elif has_quantity_data:
                    qty_field = 'quantity'
                logger.info(f"stock.quant qty field: '{qty_field}' (qty_data={has_qty_data}, quantity_data={has_quantity_data})")
        except Exception as e:
            logger.info(f"stock.quant field detection fallback to 'qty': {e}")

        try:
            test = self.client.search_read(self.odoo_db, uid, pw, 'stock.quant',
                                           [], ['id', 'reserved_quantity'], limit=1)
            if test and test[0].get('reserved_quantity') not in (False, None):
                has_reserved = True
                logger.info("stock.quant has 'reserved_quantity' with data")
            else:
                logger.info("stock.quant 'reserved_quantity' exists but no data, defaulting to 0")
        except Exception:
            logger.info("stock.quant has no 'reserved_quantity', defaulting to 0")

        fields = ['id', 'product_id', 'location_id', qty_field,
                  'in_date', 'create_date', 'create_uid', 'write_date', 'write_uid']
        if has_reserved:
            fields.append('reserved_quantity')

        # Paginate and insert in batches for progress
        max_w = cursor
        total_rows = 0
        last_id = 0
        while True:
            page_domain = domain + [('id', '>', last_id)]
            batch = self.client.search_read(self.odoo_db, uid, pw, 'stock.quant',
                                            page_domain, fields, limit=cs, offset=0, order='id asc')
            if not batch:
                break
            last_id = max(r['id'] for r in batch)
            logger.info(f"  stock.quant batch: {len(batch)} recs (last_id={last_id})")

            vals = [
                (r['id'], xid(r.get('product_id')), xid(r.get('location_id')),
                 xnum(r.get(qty_field)),
                 xnum(r.get('reserved_quantity', 0)) if has_reserved else 0,
                 xdt(r.get('in_date')),
                 xdt(r.get('create_date')), xid(r.get('create_uid')),
                 xdt(r.get('write_date')), xid(r.get('write_uid')))
                for r in batch
            ]
            sql = """INSERT INTO odoo.stock_quant (company_key,odoo_id,product_id,location_id,qty,reserved_qty,
                     in_date,odoo_create_date,odoo_create_uid,odoo_write_date,odoo_write_uid,synced_at)
                     VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                     product_id=EXCLUDED.product_id,location_id=EXCLUDED.location_id,
                     qty=EXCLUDED.qty,reserved_qty=EXCLUDED.reserved_qty,in_date=EXCLUDED.in_date,
                     odoo_create_date=EXCLUDED.odoo_create_date,odoo_create_uid=EXCLUDED.odoo_create_uid,
                     odoo_write_date=EXCLUDED.odoo_write_date,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
            template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
            n = self._batch_exec(sql, template, vals)
            total_rows += n
            max_w = self._max_wd(batch, max_w)
            logger.info(f"  stock.quant upserted: {n} (total={total_rows})")

            if len(batch) < cs:
                break

        logger.info(f"  stock.quant sync complete: {total_rows} total rows")
        return total_rows, max_w

    def _sync_res_users(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        recs = self._paginate(uid, pw, 'res.users', domain,
                              ['id','login','name','active','create_date','create_uid','write_date','write_uid'], cs,
                              ctx={'active_test': False})
        vals = [(r['id'], xtxt(r.get('login')), xtxt(r.get('name')), xbool(r.get('active')),
                 xdt(r.get('write_date')), xdt(r.get('create_date')),
                 xid(r.get('create_uid')), xid(r.get('write_uid'))) for r in recs]
        sql = """INSERT INTO odoo.res_users (company_key,odoo_id,login,name,active,odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 login=EXCLUDED.login,name=EXCLUDED.name,active=EXCLUDED.active,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_res_partner(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        fields = ['id','name','display_name','parent_id','commercial_partner_id',
                   'x_cliente_principal','x_es_principal','mayorista','x_no_llamar','x_ultima_venta',
                   'vat','phone','mobile','street','city','state_id','active',
                   'create_date','create_uid','write_date','write_uid']
        recs = self._paginate(uid, pw, 'res.partner', domain, fields, cs)
        vals = [
            (r['id'], xtxt(r.get('name')), xtxt(r.get('display_name')),
             xid(r.get('parent_id')), xid(r.get('commercial_partner_id')),
             xid(r.get('x_cliente_principal')), xbool_nullable(r.get('x_es_principal')),
             xbool_nullable(r.get('mayorista')), xbool_nullable(r.get('x_no_llamar')),
             xdt(r.get('x_ultima_venta')),
             xtxt(r.get('vat')), xtxt(r.get('phone')), xtxt(r.get('mobile')),
             xtxt(r.get('street')), xtxt(r.get('city')),
             xm2o_name(r.get('state_id')),
             xbool(r.get('active')),
             xdt(r.get('write_date')), xdt(r.get('create_date')),
             xid(r.get('create_uid')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.res_partner (company_key,odoo_id,name,display_name,parent_id,commercial_partner_id,
                 x_cliente_principal,x_es_principal,mayorista,x_no_llamar,x_ultima_venta,
                 vat,phone,mobile,street,city,state_name,active,
                 odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,display_name=EXCLUDED.display_name,parent_id=EXCLUDED.parent_id,
                 commercial_partner_id=EXCLUDED.commercial_partner_id,
                 x_cliente_principal=EXCLUDED.x_cliente_principal,x_es_principal=EXCLUDED.x_es_principal,
                 mayorista=EXCLUDED.mayorista,x_no_llamar=EXCLUDED.x_no_llamar,
                 x_ultima_venta=EXCLUDED.x_ultima_venta,
                 vat=EXCLUDED.vat,phone=EXCLUDED.phone,mobile=EXCLUDED.mobile,
                 street=EXCLUDED.street,city=EXCLUDED.city,state_name=EXCLUDED.state_name,active=EXCLUDED.active,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,
                 synced_at=now()"""
        template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_products(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')

        # Include archived products (active=False) by removing active filter
        # and using active_test=False context to bypass Odoo's default active filter
        base = [('sale_ok','=',True),('purchase_ok','=',False)]
        domain = self._inc_domain(base, cursor, mode)
        ctx_no_active = {'active_test': False}
        # x_marca is char; x_tipo is many2one; tela/entalle/hilo are many2one
        tmpl_fields = ['id','name','active','sale_ok','purchase_ok','list_price',
                        'x_marca','x_tipo','tela','entalle','hilo',
                        'create_date','create_uid','write_date','write_uid']
        recs = self._paginate(uid, pw, 'product.template', domain, tmpl_fields, cs, ctx=ctx_no_active)

        # Build name->resumen mappings for tipo, entalle, tela
        def _load_resumen_map(model, resumen_field):
            m = {}
            try:
                recs_m = self.client.search_read(self.odoo_db, uid, pw, model,
                                                 [], ['id', 'name', resumen_field], limit=200)
                for rec in recs_m:
                    name = rec.get('name') or ''
                    resumen = rec.get(resumen_field)
                    if resumen and resumen is not False:
                        m[name] = resumen
                logger.info(f"  {model} name->{resumen_field} mapping: {len(m)} entries")
            except Exception as e:
                logger.warning(f"  {model} lookup failed ({e}), using field as-is")
            return m

        tipo_map = _load_resumen_map('product.tipo', 'x_tipo_resumen')
        entalle_map = _load_resumen_map('product.entalle', 'x_entalle')
        tela_map = _load_resumen_map('product.tela', 'x_tela')

        def _resolve(val, name_map):
            if val is False or val is None:
                return None
            if isinstance(val, str):
                return name_map.get(val, val)
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                name = str(val[1])
                return name_map.get(name, name)
            return str(val)

        vals = [
            (r['id'], xtxt(r.get('name')), xbool(r.get('active')),
             xbool(r.get('sale_ok')), xbool(r.get('purchase_ok')), xnum(r.get('list_price')),
             xtxt(r.get('x_marca')),
             _resolve(r.get('x_tipo'), tipo_map),
             _resolve(r.get('tela'), tela_map),
             _resolve(r.get('entalle'), entalle_map),
             None,                              # tel: not available
             xm2o_name(r.get('hilo')),
             xdt(r.get('write_date')), xdt(r.get('create_date')),
             xid(r.get('create_uid')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.product_template (company_key,odoo_id,name,active,sale_ok,purchase_ok,list_price,
                 marca,tipo,tela,entalle,tel,hilo,odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,active=EXCLUDED.active,sale_ok=EXCLUDED.sale_ok,purchase_ok=EXCLUDED.purchase_ok,
                 list_price=EXCLUDED.list_price,marca=EXCLUDED.marca,tipo=EXCLUDED.tipo,tela=EXCLUDED.tela,
                 entalle=EXCLUDED.entalle,tel=EXCLUDED.tel,hilo=EXCLUDED.hilo,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        tmpl_template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
        tmpl_rows = self._batch_exec(sql, tmpl_template, vals)
        max_w = self._max_wd(recs, cursor)

        # B) product.product
        tmpl_ids = [r['id'] for r in recs]
        pp_rows = 0
        rel_rows = 0
        if tmpl_ids:
            pp_fields = ['id','product_tmpl_id','barcode','active',
                         'attribute_value_ids','create_date','create_uid','write_date','write_uid']
            try:
                variants = self._paginate(uid, pw, 'product.product', [('product_tmpl_id','in',tmpl_ids)], pp_fields, cs, ctx=ctx_no_active)
            except Exception:
                pp_fields.remove('attribute_value_ids')
                variants = self._paginate(uid, pw, 'product.product', [('product_tmpl_id','in',tmpl_ids)], pp_fields, cs, ctx=ctx_no_active)

            pp_vals = [
                (r['id'], xid(r.get('product_tmpl_id')), xtxt(r.get('barcode')), xbool(r.get('active')),
                 xdt(r.get('write_date')), xdt(r.get('create_date')),
                 xid(r.get('create_uid')), xid(r.get('write_uid')))
                for r in variants
            ]
            pp_sql = """INSERT INTO odoo.product_product (company_key,odoo_id,product_tmpl_id,barcode,active,
                        odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                        VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                        product_tmpl_id=EXCLUDED.product_tmpl_id,barcode=EXCLUDED.barcode,active=EXCLUDED.active,
                        odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                        odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
            pp_rows = self._batch_exec(pp_sql, "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,now())", pp_vals)
            max_w = self._max_wd(variants, max_w)

            # Variant-attribute rel
            rel_vals = []
            for r in variants:
                for av_id in (r.get('attribute_value_ids') or []):
                    rel_vals.append((r['id'], av_id))
            if rel_vals:
                rel_sql = """INSERT INTO odoo.product_attribute_value_product_product_rel
                             (company_key,product_product_id,product_attribute_value_id)
                             VALUES %s ON CONFLICT DO NOTHING"""
                rel_rows = self._batch_exec(rel_sql, "('GLOBAL',%s,%s)", rel_vals)

        return tmpl_rows + pp_rows + rel_rows, max_w

    def _sync_attributes(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        total = 0
        max_w = cursor

        # product.attribute
        recs = self._paginate(uid, pw, 'product.attribute',
                              self._inc_domain([], cursor, mode),
                              ['id','name','write_date'], cs)
        vals = [(r['id'], xtxt(r.get('name')), xdt(r.get('write_date'))) for r in recs]
        sql = """INSERT INTO odoo.product_attribute (company_key,odoo_id,name,odoo_write_date,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
        total += self._batch_exec(sql, "('GLOBAL',%s,%s,%s,now())", vals)
        max_w = self._max_wd(recs, max_w)

        # product.attribute.value
        recs = self._paginate(uid, pw, 'product.attribute.value',
                              self._inc_domain([], cursor, mode),
                              ['id','attribute_id','name','write_date'], cs)
        vals = [(r['id'], xid(r.get('attribute_id')), xtxt(r.get('name')), xdt(r.get('write_date'))) for r in recs]
        sql = """INSERT INTO odoo.product_attribute_value (company_key,odoo_id,attribute_id,name,odoo_write_date,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 attribute_id=EXCLUDED.attribute_id,name=EXCLUDED.name,
                 odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
        total += self._batch_exec(sql, "('GLOBAL',%s,%s,%s,%s,now())", vals)
        max_w = self._max_wd(recs, max_w)

        # product.template.attribute.line (may not exist in Odoo 10)
        try:
            recs = self._paginate(uid, pw, 'product.template.attribute.line',
                                  self._inc_domain([], cursor, mode),
                                  ['id','product_tmpl_id','attribute_id','write_date'], cs)
            vals = [(r['id'], xid(r.get('product_tmpl_id')), xid(r.get('attribute_id')), xdt(r.get('write_date'))) for r in recs]
            sql = """INSERT INTO odoo.product_template_attribute_line (company_key,odoo_id,product_tmpl_id,attribute_id,odoo_write_date,synced_at)
                     VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                     product_tmpl_id=EXCLUDED.product_tmpl_id,attribute_id=EXCLUDED.attribute_id,
                     odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
            total += self._batch_exec(sql, "('GLOBAL',%s,%s,%s,%s,now())", vals)
            max_w = self._max_wd(recs, max_w)
        except Exception as e:
            logger.warning(f"product.template.attribute.line not available: {e}")

        return total, max_w

    # ================================================================
    # POS
    # ================================================================

    def _sync_pos_orders(self, ck, mode, cursor, cs):
        uid, pw = self._auth(ck)
        ctx, cid = self._company_ctx(ck)
        base = [('company_id', '=', cid)] if cid else []
        domain = self._inc_domain(base, cursor, mode)

        order_fields = ['id', 'name', 'date_order', 'partner_id', 'user_id',
                        'amount_total', 'amount_tax', 'state',
                        'is_cancel', 'order_cancel', 'x_cliente_principal', 'reserva', 'reserva_use_id',
                        'location_id',
                        'company_id', 'create_date', 'create_uid', 'write_date', 'write_uid']

        max_w = cursor
        total_orders = 0
        total_lines = 0

        # ID-based pagination (stable, no duplicates)
        last_id = 0
        batch_errors = 0
        while True:
            try:
                page_domain = domain + [('id', '>', last_id)]
                orders = self.client.search_read(self.odoo_db, uid, pw, 'pos.order', page_domain, order_fields,
                                                 limit=cs, offset=0, order='id asc', context=ctx)
                if not orders:
                    break

                last_id = max(r['id'] for r in orders)
                logger.info(f"  POS orders batch: {len(orders)} (last_id={last_id})")

                o_vals = [
                    (ck, r['id'], xtxt(r.get('name')), xdt(r.get('date_order')),
                     xid(r.get('partner_id')), xid(r.get('user_id')),
                     xnum(r.get('amount_total')), xnum(r.get('amount_tax')),
                     xtxt(r.get('state')),
                     xbool_nullable(r.get('is_cancel')), xbool_nullable(r.get('order_cancel')),
                     xid(r.get('x_cliente_principal')), xbool_nullable(r.get('reserva')),
                     xid(r.get('reserva_use_id')),
                     xid(r.get('location_id')),
                     xdt(r.get('write_date')), xdt(r.get('create_date')),
                     xid(r.get('create_uid')), xid(r.get('write_uid')))
                    for r in orders
                ]
                o_sql = """INSERT INTO odoo.pos_order (company_key,odoo_id,name,date_order,partner_id,user_id,
                           amount_total,amount_tax,state,is_cancel,order_cancel,
                           x_cliente_principal,reserva,reserva_use_id,location_id,
                           odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                           VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                           name=EXCLUDED.name,date_order=EXCLUDED.date_order,partner_id=EXCLUDED.partner_id,
                           user_id=EXCLUDED.user_id,amount_total=EXCLUDED.amount_total,amount_tax=EXCLUDED.amount_tax,
                           state=EXCLUDED.state,is_cancel=EXCLUDED.is_cancel,order_cancel=EXCLUDED.order_cancel,
                           x_cliente_principal=EXCLUDED.x_cliente_principal,reserva=EXCLUDED.reserva,
                           reserva_use_id=EXCLUDED.reserva_use_id,location_id=EXCLUDED.location_id,
                           odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                           odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
                total_orders += self._batch_exec(o_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", o_vals)
                max_w = self._max_wd(orders, max_w)

                # Lines for this batch
                oids = [r['id'] for r in orders]
                if oids:
                    lines = self._paginate(uid, pw, 'pos.order.line', [('order_id', 'in', oids)],
                                           ['id', 'order_id', 'product_id', 'qty', 'price_unit', 'discount', 'price_subtotal', 'write_date'], cs)
                    l_vals = [
                        (ck, l['id'], xid(l.get('order_id')), xid(l.get('product_id')),
                         xnum(l.get('qty')), xnum(l.get('price_unit')),
                         xnum(l.get('discount')), xnum(l.get('price_subtotal')),
                         xdt(l.get('write_date')))
                        for l in lines
                    ]
                    l_sql = """INSERT INTO odoo.pos_order_line (company_key,odoo_id,order_id,product_id,qty,price_unit,
                               discount,price_subtotal,odoo_write_date,synced_at)
                               VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                               order_id=EXCLUDED.order_id,product_id=EXCLUDED.product_id,qty=EXCLUDED.qty,
                               price_unit=EXCLUDED.price_unit,discount=EXCLUDED.discount,
                               price_subtotal=EXCLUDED.price_subtotal,odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
                    total_lines += self._batch_exec(l_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", l_vals)

                batch_errors = 0  # reset on success
                if len(orders) < cs:
                    break
                time.sleep(0.3)  # gentle on Odoo server

            except Exception as e:
                batch_errors += 1
                if batch_errors >= 3:
                    logger.error(f"  POS batch failed 3 times at last_id={last_id}, aborting: {e}")
                    raise
                wait = 30 * batch_errors
                logger.warning(f"  POS batch error at last_id={last_id} ({batch_errors}/3), retrying in {wait}s: {e}")
                time.sleep(wait)

        return total_orders + total_lines, max_w

    # ================================================================
    # CREDIT INVOICES (account.invoice con is_credit=True)
    # ================================================================

    def _sync_credit_invoices(self, ck, mode, cursor, cs):
        uid, pw = self._auth(ck)
        ctx, cid = self._company_ctx(ck)
        base = [('is_credit', '=', True), ('type', '=', 'out_invoice')]
        if cid:
            base.append(('company_id', '=', cid))
        domain = self._inc_domain(base, cursor, mode)

        inv_fields = ['id', 'number', 'date_invoice', 'partner_id', 'user_id',
                       'company_id', 'state', 'amount_total', 'residual',
                       'payment_term_id', 'currency_id',
                       'create_date', 'create_uid', 'write_date', 'write_uid']

        max_w = cursor
        total_inv = 0
        total_lines = 0

        last_id = 0
        batch_errors = 0
        while True:
            try:
                page_domain = domain + [('id', '>', last_id)]
                invoices = self.client.search_read(self.odoo_db, uid, pw, 'account.invoice',
                                                   page_domain, inv_fields,
                                                   limit=cs, offset=0, order='id asc', context=ctx)
                if not invoices:
                    break

                last_id = max(r['id'] for r in invoices)
                logger.info(f"  Credit invoices batch: {len(invoices)} (last_id={last_id})")

                inv_vals = [
                    (ck, r['id'], xtxt(r.get('number')),
                     r.get('date_invoice') if r.get('date_invoice') else None,
                     xid(r.get('partner_id')), xid(r.get('user_id')),
                     xid(r.get('company_id')), xtxt(r.get('state')),
                     xnum(r.get('amount_total')), xnum(r.get('residual')),
                     xid(r.get('payment_term_id')), xid(r.get('currency_id')),
                     xdt(r.get('create_date')), xid(r.get('create_uid')),
                     xdt(r.get('write_date')), xid(r.get('write_uid')))
                    for r in invoices
                ]
                inv_sql = """INSERT INTO odoo.account_invoice_credit
                    (company_key, odoo_id, number, date_invoice, partner_id, user_id,
                     company_id, state, amount_total, amount_residual,
                     payment_term_id, currency_id,
                     odoo_create_date, odoo_create_uid, odoo_write_date, odoo_write_uid, synced_at)
                    VALUES %s ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                     number=EXCLUDED.number, date_invoice=EXCLUDED.date_invoice,
                     partner_id=EXCLUDED.partner_id, user_id=EXCLUDED.user_id,
                     company_id=EXCLUDED.company_id, state=EXCLUDED.state,
                     amount_total=EXCLUDED.amount_total, amount_residual=EXCLUDED.amount_residual,
                     payment_term_id=EXCLUDED.payment_term_id, currency_id=EXCLUDED.currency_id,
                     odoo_create_date=EXCLUDED.odoo_create_date, odoo_create_uid=EXCLUDED.odoo_create_uid,
                     odoo_write_date=EXCLUDED.odoo_write_date, odoo_write_uid=EXCLUDED.odoo_write_uid,
                     synced_at=now()"""
                total_inv += self._batch_exec(inv_sql,
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", inv_vals)
                max_w = self._max_wd(invoices, max_w)

                # Lines for this batch
                inv_ids = [r['id'] for r in invoices]
                if inv_ids:
                    lines = self._paginate(uid, pw, 'account.invoice.line',
                        [('invoice_id', 'in', inv_ids)],
                        ['id', 'invoice_id', 'product_id', 'name', 'quantity',
                         'price_unit', 'discount', 'price_subtotal',
                         'create_date', 'create_uid', 'write_date', 'write_uid'], cs)
                    l_vals = [
                        (ck, l['id'], xid(l.get('invoice_id')), xid(l.get('product_id')),
                         xtxt(l.get('name')), xnum(l.get('quantity')),
                         xnum(l.get('price_unit')), xnum(l.get('discount')),
                         xnum(l.get('price_subtotal')),
                         xdt(l.get('create_date')), xid(l.get('create_uid')),
                         xdt(l.get('write_date')), xid(l.get('write_uid')))
                        for l in lines
                    ]
                    l_sql = """INSERT INTO odoo.account_invoice_credit_line
                        (company_key, odoo_id, invoice_id, product_id, name, quantity,
                         price_unit, discount, price_subtotal,
                         odoo_create_date, odoo_create_uid, odoo_write_date, odoo_write_uid, synced_at)
                        VALUES %s ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                         invoice_id=EXCLUDED.invoice_id, product_id=EXCLUDED.product_id,
                         name=EXCLUDED.name, quantity=EXCLUDED.quantity,
                         price_unit=EXCLUDED.price_unit, discount=EXCLUDED.discount,
                         price_subtotal=EXCLUDED.price_subtotal,
                         odoo_create_date=EXCLUDED.odoo_create_date, odoo_create_uid=EXCLUDED.odoo_create_uid,
                         odoo_write_date=EXCLUDED.odoo_write_date, odoo_write_uid=EXCLUDED.odoo_write_uid,
                         synced_at=now()"""
                    total_lines += self._batch_exec(l_sql,
                        "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", l_vals)

                batch_errors = 0
                if len(invoices) < cs:
                    break
                time.sleep(0.3)

            except Exception as e:
                batch_errors += 1
                if batch_errors >= 3:
                    logger.error(f"  Credit inv batch failed 3x at last_id={last_id}: {e}")
                    raise
                wait = 30 * batch_errors
                logger.warning(f"  Credit inv batch error at last_id={last_id} ({batch_errors}/3), retry in {wait}s: {e}")
                time.sleep(wait)

        return total_inv + total_lines, max_w

    # ---- Batch exec helper ----

    def _batch_exec(self, sql, template, values, page_size=1000):
        if not values:
            return 0
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                execute_values(cur, sql, values, template=template, page_size=page_size)
            conn.commit()
            return len(values)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
