"""
Odoo -> PostgreSQL Sync Engine.
Handles incremental sync for masters (GLOBAL) and POS (per company).
"""
import os
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
from odoo_client import OdooClient

logger = logging.getLogger(__name__)

MASTER_JOBS = ['RES_COMPANY', 'RES_USERS', 'RES_PARTNER', 'PRODUCTS', 'ATTRIBUTES']
POS_JOBS = ['POS_ORDERS']

ADVISORY_LOCK_ID = 777777


def extract_id(val):
    """Extract integer id from Odoo many2one field ([id, name] or int or False)."""
    if val is False or val is None:
        return None
    if isinstance(val, (list, tuple)) and len(val) >= 1:
        return val[0]
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    return None


def extract_date(val):
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


def extract_bool(val):
    """Extract boolean, treating Odoo False as Python False/None."""
    if val is False or val is None:
        return False
    return bool(val)


def extract_text(val):
    """Extract text, treating Odoo False as None."""
    if val is False or val is None:
        return None
    return str(val)


def extract_numeric(val):
    """Extract numeric value."""
    if val is False or val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class SyncService:
    def __init__(self):
        self.pg_url = os.environ['PG_URL']
        self.odoo_url = os.environ['ODOO_URL']
        self.odoo_db = os.environ['ODOO_DB']
        self.client = OdooClient(self.odoo_url)

        # Credentials per company
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
        # Cache for authenticated uids and company contexts
        self._uid_cache = {}
        self._company_context_cache = {}

    def _get_pg_conn(self):
        return psycopg2.connect(self.pg_url)

    def _auth(self, company_key):
        """Authenticate for a given company key and return (uid, password)."""
        if company_key in self._uid_cache:
            return self._uid_cache[company_key]
        creds = self.credentials.get(company_key, self.credentials['Ambission'])
        uid = self.client.authenticate(self.odoo_db, creds['login'], creds['password'])
        self._uid_cache[company_key] = (uid, creds['password'])
        return uid, creds['password']

    def _get_company_context(self, company_key):
        """Get company context for POS calls."""
        if company_key in self._company_context_cache:
            return self._company_context_cache[company_key]
        uid, password = self._auth(company_key)
        try:
            user_data = self.client.read(
                self.odoo_db, uid, password, 'res.users', [uid],
                ['company_id', 'company_ids']
            )
            if user_data:
                company_id = extract_id(user_data[0].get('company_id'))
                company_ids = user_data[0].get('company_ids', [])
                if not company_ids:
                    company_ids = [company_id] if company_id else []
                ctx = {
                    'allowed_company_ids': company_ids,
                    'company_id': company_id,
                }
                self._company_context_cache[company_key] = (ctx, company_id)
                logger.info(f"Company context for {company_key}: company_id={company_id}, ids={company_ids}")
                return ctx, company_id
        except Exception as e:
            logger.warning(f"Could not get company context for {company_key}: {e}")
        ctx = {}
        self._company_context_cache[company_key] = (ctx, None)
        return ctx, None

    def _insert_log(self, conn, job_code, company_key):
        """Insert a sync_run_log entry and return its id."""
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO odoo.sync_run_log (job_code, company_key, started_at, status)
                VALUES (%s, %s, now(), 'RUNNING')
                RETURNING id
            """, (job_code, company_key))
            log_id = cur.fetchone()[0]
        return log_id

    def _finish_log(self, conn, log_id, status, rows_upserted=0, rows_updated=0, error_message=None):
        """Update sync_run_log with final status."""
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE odoo.sync_run_log
                SET ended_at = now(), status = %s, rows_upserted = %s, rows_updated = %s, error_message = %s
                WHERE id = %s
            """, (status, rows_upserted, rows_updated, error_message, log_id))

    def _update_job_cursor(self, conn, job_code, last_cursor, success=True, error=None):
        """Update sync_job after a run."""
        with conn.cursor() as cur:
            if success:
                cur.execute("""
                    UPDATE odoo.sync_job
                    SET last_run_at = now(), last_success_at = now(), last_cursor = %s, last_error = NULL
                    WHERE job_code = %s
                """, (last_cursor, job_code))
            else:
                cur.execute("""
                    UPDATE odoo.sync_job
                    SET last_run_at = now(), last_error = %s
                    WHERE job_code = %s
                """, (str(error)[:500] if error else None, job_code))

    def _get_job_cursor(self, conn, job_code):
        """Get last_cursor for a job."""
        with conn.cursor() as cur:
            cur.execute("SELECT last_cursor FROM odoo.sync_job WHERE job_code = %s", (job_code,))
            row = cur.fetchone()
            return row[0] if row else None

    def _build_incremental_domain(self, base_domain, last_cursor, mode):
        """Add write_date filter for incremental mode."""
        domain = list(base_domain)
        if mode == 'INCREMENTAL' and last_cursor:
            cursor_str = last_cursor.strftime('%Y-%m-%d %H:%M:%S')
            domain.append(('write_date', '>', cursor_str))
        return domain

    def run_sync(self, job_code=None, mode=None, target='ALL', company_key=None):
        """Main entry point. Returns summary dict."""
        conn = self._get_pg_conn()
        conn.autocommit = True  # Use autocommit to avoid stale transaction issues
        results = []
        try:
            # Advisory lock
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
                locked = cur.fetchone()[0]
            if not locked:
                return {"success": False, "message": "Otra sincronización en curso. Intente más tarde.", "results": []}

            # Read jobs
            with conn.cursor() as cur:
                if job_code:
                    cur.execute("SELECT job_code, mode, chunk_size FROM odoo.sync_job WHERE job_code = %s AND enabled = true ORDER BY priority", (job_code,))
                else:
                    cur.execute("SELECT job_code, mode, chunk_size FROM odoo.sync_job WHERE enabled = true ORDER BY priority")
                jobs = cur.fetchall()

            for jc, job_mode, chunk_size in jobs:
                effective_mode = mode or job_mode
                is_master = jc in MASTER_JOBS
                is_pos = jc in POS_JOBS

                # Filter by target
                if target == 'GLOBAL_ONLY' and not is_master:
                    continue
                if target == 'POS_ONLY' and not is_pos:
                    continue

                if is_master:
                    result = self._run_job(conn, jc, 'GLOBAL', effective_mode, chunk_size)
                    results.append(result)
                elif is_pos:
                    if company_key:
                        result = self._run_job(conn, jc, company_key, effective_mode, chunk_size)
                        results.append(result)
                    else:
                        for ck in ['Ambission', 'ProyectoModa']:
                            result = self._run_job(conn, jc, ck, effective_mode, chunk_size)
                            results.append(result)

            return {
                "success": True,
                "message": f"Sincronización completada: {len(results)} ejecuciones",
                "results": results,
            }
        except Exception as e:
            logger.error(f"Sync engine error: {e}", exc_info=True)
            return {"success": False, "message": str(e), "results": results}
        finally:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,))
            except Exception:
                pass
            conn.close()

    def _run_job(self, conn, job_code, company_key, mode, chunk_size):
        """Run a single job for a specific company_key."""
        log_id = self._insert_log(conn, job_code, company_key)
        logger.info(f"Starting sync: {job_code} / {company_key} / {mode}")
        try:
            last_cursor = self._get_job_cursor(conn, job_code) if mode == 'INCREMENTAL' else None

            handler = {
                'RES_COMPANY': self._sync_res_company,
                'RES_USERS': self._sync_res_users,
                'RES_PARTNER': self._sync_res_partner,
                'PRODUCTS': self._sync_products,
                'ATTRIBUTES': self._sync_attributes,
                'POS_ORDERS': self._sync_pos_orders,
            }.get(job_code)

            if not handler:
                raise Exception(f"Unknown job_code: {job_code}")

            if job_code in POS_JOBS:
                rows_upserted, new_cursor = handler(conn, company_key, mode, last_cursor, chunk_size)
            else:
                rows_upserted, new_cursor = handler(conn, mode, last_cursor, chunk_size)

            self._finish_log(conn, log_id, 'OK', rows_upserted=rows_upserted)
            if new_cursor:
                self._update_job_cursor(conn, job_code, new_cursor, success=True)
            else:
                self._update_job_cursor(conn, job_code, last_cursor, success=True)

            logger.info(f"Sync OK: {job_code}/{company_key} -> {rows_upserted} rows")
            return {"job_code": job_code, "company_key": company_key, "status": "OK", "rows": rows_upserted}

        except Exception as e:
            logger.error(f"Sync ERROR: {job_code}/{company_key}: {e}", exc_info=True)
            self._finish_log(conn, log_id, 'ERROR', error_message=str(e)[:500])
            self._update_job_cursor(conn, job_code, None, success=False, error=e)
            return {"job_code": job_code, "company_key": company_key, "status": "ERROR", "error": str(e)[:200]}

    # ----------------------------------------------------------------
    # MASTER SYNCS (company_key='GLOBAL')
    # ----------------------------------------------------------------

    def _sync_res_company(self, conn, mode, last_cursor, chunk_size):
        uid, password = self._auth('Ambission')
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = ['id', 'name', 'active', 'create_date', 'create_uid', 'write_date', 'write_uid']
        records = self._paginate_read(uid, password, 'res.company', domain, fields, chunk_size)
        max_write = last_cursor
        rows = 0
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.res_company (company_key, odoo_id, name, active, odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at)
                    VALUES ('GLOBAL', %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        name = EXCLUDED.name, active = EXCLUDED.active,
                        odoo_write_date = EXCLUDED.odoo_write_date,
                        odoo_create_date = EXCLUDED.odoo_create_date,
                        odoo_create_uid = EXCLUDED.odoo_create_uid,
                        odoo_write_uid = EXCLUDED.odoo_write_uid,
                        synced_at = now()
                """, (
                    rec['id'], extract_text(rec.get('name')), extract_bool(rec.get('active')),
                    wd, extract_date(rec.get('create_date')),
                    extract_id(rec.get('create_uid')), extract_id(rec.get('write_uid')),
                ))
            rows += 1

        return rows, max_write

    def _sync_res_users(self, conn, mode, last_cursor, chunk_size):
        uid, password = self._auth('Ambission')
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = ['id', 'login', 'name', 'active', 'create_date', 'create_uid', 'write_date', 'write_uid']
        records = self._paginate_read(uid, password, 'res.users', domain, fields, chunk_size)
        max_write = last_cursor
        rows = 0
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.res_users (company_key, odoo_id, login, name, active, odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at)
                    VALUES ('GLOBAL', %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        login = EXCLUDED.login, name = EXCLUDED.name, active = EXCLUDED.active,
                        odoo_write_date = EXCLUDED.odoo_write_date,
                        odoo_create_date = EXCLUDED.odoo_create_date,
                        odoo_create_uid = EXCLUDED.odoo_create_uid,
                        odoo_write_uid = EXCLUDED.odoo_write_uid,
                        synced_at = now()
                """, (
                    rec['id'], extract_text(rec.get('login')), extract_text(rec.get('name')),
                    extract_bool(rec.get('active')), wd,
                    extract_date(rec.get('create_date')),
                    extract_id(rec.get('create_uid')), extract_id(rec.get('write_uid')),
                ))
            rows += 1

        return rows, max_write

    def _sync_res_partner(self, conn, mode, last_cursor, chunk_size):
        uid, password = self._auth('Ambission')
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = [
            'id', 'name', 'display_name', 'parent_id', 'commercial_partner_id',
            'x_cliente_principal', 'x_es_principal', 'mayorista', 'x_no_llamar', 'x_ultima_venta',
            'vat', 'phone', 'mobile', 'street', 'city', 'active',
            'create_date', 'create_uid', 'write_date', 'write_uid',
        ]
        records = self._paginate_read(uid, password, 'res.partner', domain, fields, chunk_size)
        max_write = last_cursor
        rows = 0
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.res_partner (
                        company_key, odoo_id, name, display_name, parent_id, commercial_partner_id,
                        x_cliente_principal, x_es_principal, mayorista, x_no_llamar, x_ultima_venta,
                        vat, phone, mobile, street, city, active,
                        odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at
                    ) VALUES (
                        'GLOBAL', %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, now()
                    )
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        name=EXCLUDED.name, display_name=EXCLUDED.display_name,
                        parent_id=EXCLUDED.parent_id, commercial_partner_id=EXCLUDED.commercial_partner_id,
                        x_cliente_principal=EXCLUDED.x_cliente_principal, x_es_principal=EXCLUDED.x_es_principal,
                        mayorista=EXCLUDED.mayorista, x_no_llamar=EXCLUDED.x_no_llamar,
                        x_ultima_venta=EXCLUDED.x_ultima_venta,
                        vat=EXCLUDED.vat, phone=EXCLUDED.phone, mobile=EXCLUDED.mobile,
                        street=EXCLUDED.street, city=EXCLUDED.city, active=EXCLUDED.active,
                        odoo_write_date=EXCLUDED.odoo_write_date,
                        odoo_create_date=EXCLUDED.odoo_create_date,
                        odoo_create_uid=EXCLUDED.odoo_create_uid,
                        odoo_write_uid=EXCLUDED.odoo_write_uid,
                        synced_at=now()
                """, (
                    rec['id'],
                    extract_text(rec.get('name')), extract_text(rec.get('display_name')),
                    extract_id(rec.get('parent_id')), extract_id(rec.get('commercial_partner_id')),
                    extract_id(rec.get('x_cliente_principal')),
                    extract_bool(rec.get('x_es_principal')) if rec.get('x_es_principal') is not False else None,
                    extract_bool(rec.get('mayorista')) if rec.get('mayorista') is not False else None,
                    extract_bool(rec.get('x_no_llamar')) if rec.get('x_no_llamar') is not False else None,
                    extract_date(rec.get('x_ultima_venta')),
                    extract_text(rec.get('vat')), extract_text(rec.get('phone')),
                    extract_text(rec.get('mobile')), extract_text(rec.get('street')),
                    extract_text(rec.get('city')), extract_bool(rec.get('active')),
                    wd, extract_date(rec.get('create_date')),
                    extract_id(rec.get('create_uid')), extract_id(rec.get('write_uid')),
                ))
            rows += 1

        return rows, max_write

    def _sync_products(self, conn, mode, last_cursor, chunk_size):
        uid, password = self._auth('Ambission')

        # A) product.template
        base_domain = [('sale_ok', '=', True), ('purchase_ok', '=', False), ('active', '=', True)]
        domain = self._build_incremental_domain(base_domain, last_cursor, mode)

        tmpl_fields = [
            'id', 'name', 'active', 'sale_ok', 'purchase_ok', 'list_price',
            'create_date', 'create_uid', 'write_date', 'write_uid',
        ]
        # Try custom fields - they might have x_ prefix or not
        custom_fields = ['marca', 'tipo', 'tela', 'entalle', 'tel', 'hilo']
        custom_x_fields = ['x_marca', 'x_tipo', 'x_tela', 'x_entalle', 'x_tel', 'x_hilo']

        # Try with x_ prefix first (common in Odoo 10 custom fields)
        try:
            test_fields = tmpl_fields + custom_x_fields
            self.client.search_read(self.odoo_db, uid, password, 'product.template', [('id', '=', 1)], test_fields, limit=1)
            actual_custom = custom_x_fields
            custom_mapping = dict(zip(custom_fields, custom_x_fields))
        except Exception:
            # Try without prefix
            try:
                test_fields = tmpl_fields + custom_fields
                self.client.search_read(self.odoo_db, uid, password, 'product.template', [('id', '=', 1)], test_fields, limit=1)
                actual_custom = custom_fields
                custom_mapping = dict(zip(custom_fields, custom_fields))
            except Exception:
                actual_custom = []
                custom_mapping = {}
                logger.warning("Custom product fields not found, skipping marca/tipo/tela/entalle/tel/hilo")

        all_tmpl_fields = tmpl_fields + actual_custom
        templates = self._paginate_read(uid, password, 'product.template', domain, all_tmpl_fields, chunk_size)

        max_write = last_cursor
        tmpl_rows = 0
        tmpl_ids = []

        for rec in templates:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            tmpl_ids.append(rec['id'])

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.product_template (
                        company_key, odoo_id, name, active, sale_ok, purchase_ok, list_price,
                        marca, tipo, tela, entalle, tel, hilo,
                        odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at
                    ) VALUES ('GLOBAL', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        name=EXCLUDED.name, active=EXCLUDED.active, sale_ok=EXCLUDED.sale_ok,
                        purchase_ok=EXCLUDED.purchase_ok, list_price=EXCLUDED.list_price,
                        marca=EXCLUDED.marca, tipo=EXCLUDED.tipo, tela=EXCLUDED.tela,
                        entalle=EXCLUDED.entalle, tel=EXCLUDED.tel, hilo=EXCLUDED.hilo,
                        odoo_write_date=EXCLUDED.odoo_write_date,
                        odoo_create_date=EXCLUDED.odoo_create_date,
                        odoo_create_uid=EXCLUDED.odoo_create_uid,
                        odoo_write_uid=EXCLUDED.odoo_write_uid,
                        synced_at=now()
                """, (
                    rec['id'], extract_text(rec.get('name')),
                    extract_bool(rec.get('active')), extract_bool(rec.get('sale_ok')),
                    extract_bool(rec.get('purchase_ok')), extract_numeric(rec.get('list_price')),
                    extract_text(rec.get(custom_mapping.get('marca', 'marca'))),
                    extract_text(rec.get(custom_mapping.get('tipo', 'tipo'))),
                    extract_text(rec.get(custom_mapping.get('tela', 'tela'))),
                    extract_text(rec.get(custom_mapping.get('entalle', 'entalle'))),
                    extract_text(rec.get(custom_mapping.get('tel', 'tel'))),
                    extract_text(rec.get(custom_mapping.get('hilo', 'hilo'))),
                    wd, extract_date(rec.get('create_date')),
                    extract_id(rec.get('create_uid')), extract_id(rec.get('write_uid')),
                ))
            tmpl_rows += 1


        # B) product.product (variants of fetched templates)
        pp_rows = 0
        if tmpl_ids:
            pp_domain = [('product_tmpl_id', 'in', tmpl_ids)]
            pp_fields = [
                'id', 'product_tmpl_id', 'barcode', 'active',
                'attribute_value_ids',
                'create_date', 'create_uid', 'write_date', 'write_uid',
            ]
            try:
                variants = self._paginate_read(uid, password, 'product.product', pp_domain, pp_fields, chunk_size)
            except Exception:
                # attribute_value_ids might not exist in Odoo 10
                pp_fields.remove('attribute_value_ids')
                variants = self._paginate_read(uid, password, 'product.product', pp_domain, pp_fields, chunk_size)

            for rec in variants:
                wd = extract_date(rec.get('write_date'))
                if wd and (max_write is None or wd > max_write):
                    max_write = wd
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO odoo.product_product (
                            company_key, odoo_id, product_tmpl_id, barcode, active,
                            odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at
                        ) VALUES ('GLOBAL', %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                            product_tmpl_id=EXCLUDED.product_tmpl_id, barcode=EXCLUDED.barcode,
                            active=EXCLUDED.active, odoo_write_date=EXCLUDED.odoo_write_date,
                            odoo_create_date=EXCLUDED.odoo_create_date,
                            odoo_create_uid=EXCLUDED.odoo_create_uid,
                            odoo_write_uid=EXCLUDED.odoo_write_uid,
                            synced_at=now()
                    """, (
                        rec['id'], extract_id(rec.get('product_tmpl_id')),
                        extract_text(rec.get('barcode')), extract_bool(rec.get('active')),
                        wd, extract_date(rec.get('create_date')),
                        extract_id(rec.get('create_uid')), extract_id(rec.get('write_uid')),
                    ))
                pp_rows += 1

                # Populate variant-attribute rel
                attr_val_ids = rec.get('attribute_value_ids', [])
                if attr_val_ids:
                    for av_id in attr_val_ids:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO odoo.product_attribute_value_product_product_rel
                                    (company_key, product_product_id, product_attribute_value_id)
                                VALUES ('GLOBAL', %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (rec['id'], av_id))
    

        return tmpl_rows + pp_rows, max_write

    def _sync_attributes(self, conn, mode, last_cursor, chunk_size):
        uid, password = self._auth('Ambission')
        total_rows = 0

        # 1) product.attribute
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = ['id', 'name', 'create_date', 'create_uid', 'write_date', 'write_uid']
        max_write = last_cursor

        records = self._paginate_read(uid, password, 'product.attribute', domain, fields, chunk_size)
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.product_attribute (company_key, odoo_id, name, odoo_write_date, synced_at)
                    VALUES ('GLOBAL', %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        name=EXCLUDED.name, odoo_write_date=EXCLUDED.odoo_write_date, synced_at=now()
                """, (rec['id'], extract_text(rec.get('name')), wd))
            total_rows += 1


        # 2) product.attribute.value
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = ['id', 'attribute_id', 'name', 'create_date', 'create_uid', 'write_date', 'write_uid']
        records = self._paginate_read(uid, password, 'product.attribute.value', domain, fields, chunk_size)
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.product_attribute_value (company_key, odoo_id, attribute_id, name, odoo_write_date, synced_at)
                    VALUES ('GLOBAL', %s, %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        attribute_id=EXCLUDED.attribute_id, name=EXCLUDED.name,
                        odoo_write_date=EXCLUDED.odoo_write_date, synced_at=now()
                """, (rec['id'], extract_id(rec.get('attribute_id')), extract_text(rec.get('name')), wd))
            total_rows += 1


        # 3) product.template.attribute.line
        domain = self._build_incremental_domain([], last_cursor, mode)
        fields = ['id', 'product_tmpl_id', 'attribute_id', 'create_date', 'create_uid', 'write_date', 'write_uid']
        records = self._paginate_read(uid, password, 'product.template.attribute.line', domain, fields, chunk_size)
        for rec in records:
            wd = extract_date(rec.get('write_date'))
            if wd and (max_write is None or wd > max_write):
                max_write = wd
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO odoo.product_template_attribute_line (
                        company_key, odoo_id, product_tmpl_id, attribute_id, odoo_write_date, synced_at
                    ) VALUES ('GLOBAL', %s, %s, %s, %s, now())
                    ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                        product_tmpl_id=EXCLUDED.product_tmpl_id, attribute_id=EXCLUDED.attribute_id,
                        odoo_write_date=EXCLUDED.odoo_write_date, synced_at=now()
                """, (
                    rec['id'], extract_id(rec.get('product_tmpl_id')),
                    extract_id(rec.get('attribute_id')), wd,
                ))
            total_rows += 1


        return total_rows, max_write

    # ----------------------------------------------------------------
    # POS SYNC (per company)
    # ----------------------------------------------------------------

    def _sync_pos_orders(self, conn, company_key, mode, last_cursor, chunk_size):
        uid, password = self._auth(company_key)
        ctx, company_id = self._get_company_context(company_key)

        # Build domain
        base_domain = []
        if company_id:
            base_domain.append(('company_id', '=', company_id))
        domain = self._build_incremental_domain(base_domain, last_cursor, mode)

        order_fields = [
            'id', 'name', 'date_order', 'partner_id', 'user_id',
            'amount_total', 'amount_tax', 'state',
            'is_cancel', 'order_cancel', 'x_cliente_principal', 'reserva', 'reserva_use_id',
            'company_id',
            'create_date', 'create_uid', 'write_date', 'write_uid',
        ]

        max_write = last_cursor
        order_rows = 0
        line_rows = 0

        # Paginated fetch of orders
        offset = 0
        while True:
            orders = self.client.search_read(
                self.odoo_db, uid, password, 'pos.order', domain, order_fields,
                limit=chunk_size, offset=offset, order='write_date asc', context=ctx,
            )
            if not orders:
                break

            order_ids = []
            for rec in orders:
                wd = extract_date(rec.get('write_date'))
                if wd and (max_write is None or wd > max_write):
                    max_write = wd
                order_ids.append(rec['id'])

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO odoo.pos_order (
                            company_key, odoo_id, name, date_order, partner_id, user_id,
                            amount_total, amount_tax, state, is_cancel, order_cancel,
                            x_cliente_principal, reserva, reserva_use_id,
                            odoo_write_date, odoo_create_date, odoo_create_uid, odoo_write_uid, synced_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                            name=EXCLUDED.name, date_order=EXCLUDED.date_order,
                            partner_id=EXCLUDED.partner_id, user_id=EXCLUDED.user_id,
                            amount_total=EXCLUDED.amount_total, amount_tax=EXCLUDED.amount_tax,
                            state=EXCLUDED.state, is_cancel=EXCLUDED.is_cancel, order_cancel=EXCLUDED.order_cancel,
                            x_cliente_principal=EXCLUDED.x_cliente_principal,
                            reserva=EXCLUDED.reserva, reserva_use_id=EXCLUDED.reserva_use_id,
                            odoo_write_date=EXCLUDED.odoo_write_date,
                            odoo_create_date=EXCLUDED.odoo_create_date,
                            odoo_create_uid=EXCLUDED.odoo_create_uid,
                            odoo_write_uid=EXCLUDED.odoo_write_uid,
                            synced_at=now()
                    """, (
                        company_key, rec['id'],
                        extract_text(rec.get('name')),
                        extract_date(rec.get('date_order')),
                        extract_id(rec.get('partner_id')),
                        extract_id(rec.get('user_id')),
                        extract_numeric(rec.get('amount_total')),
                        extract_numeric(rec.get('amount_tax')),
                        extract_text(rec.get('state')),
                        extract_bool(rec.get('is_cancel')) if rec.get('is_cancel') is not False else None,
                        extract_bool(rec.get('order_cancel')) if rec.get('order_cancel') is not False else None,
                        extract_id(rec.get('x_cliente_principal')),
                        extract_bool(rec.get('reserva')) if rec.get('reserva') is not False else None,
                        extract_id(rec.get('reserva_use_id')),
                        wd,
                        extract_date(rec.get('create_date')),
                        extract_id(rec.get('create_uid')),
                        extract_id(rec.get('write_uid')),
                    ))
                order_rows += 1
    

            # Fetch lines for this batch of orders
            if order_ids:
                line_fields = [
                    'id', 'order_id', 'product_id', 'qty', 'price_unit', 'discount', 'price_subtotal',
                    'create_date', 'create_uid', 'write_date', 'write_uid',
                ]
                lines = self._paginate_read(
                    uid, password, 'pos.order.line',
                    [('order_id', 'in', order_ids)], line_fields, chunk_size
                )
                for line in lines:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO odoo.pos_order_line (
                                company_key, odoo_id, order_id, product_id, qty, price_unit,
                                discount, price_subtotal, odoo_write_date, synced_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                            ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                                order_id=EXCLUDED.order_id, product_id=EXCLUDED.product_id,
                                qty=EXCLUDED.qty, price_unit=EXCLUDED.price_unit,
                                discount=EXCLUDED.discount, price_subtotal=EXCLUDED.price_subtotal,
                                odoo_write_date=EXCLUDED.odoo_write_date, synced_at=now()
                        """, (
                            company_key, line['id'],
                            extract_id(line.get('order_id')),
                            extract_id(line.get('product_id')),
                            extract_numeric(line.get('qty')),
                            extract_numeric(line.get('price_unit')),
                            extract_numeric(line.get('discount')),
                            extract_numeric(line.get('price_subtotal')),
                            extract_date(line.get('write_date')),
                        ))
                    line_rows += 1
        

            offset += chunk_size
            if len(orders) < chunk_size:
                break

        return order_rows + line_rows, max_write

    # ----------------------------------------------------------------
    # Helper: paginated search_read
    # ----------------------------------------------------------------

    def _paginate_read(self, uid, password, model, domain, fields, chunk_size, context=None):
        """Fetch all records matching domain using pagination."""
        all_records = []
        offset = 0
        while True:
            batch = self.client.search_read(
                self.odoo_db, uid, password, model, domain, fields,
                limit=chunk_size, offset=offset, context=context,
            )
            if not batch:
                break
            all_records.extend(batch)
            offset += chunk_size
            if len(batch) < chunk_size:
                break
        logger.info(f"  Fetched {len(all_records)} records from {model}")
        return all_records
