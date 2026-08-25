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

MASTER_JOBS = ['RES_COMPANY', 'RES_USERS', 'RES_PARTNER', 'X_LINEA_NEGOCIO', 'PRODUCTS', 'ATTRIBUTES', 'STOCK_LOCATIONS', 'STOCK_QUANTS', 'STOCK_INVENTORY', 'STOCK_MOVE']
POS_JOBS = ['POS_ORDERS']
MULTI_JOBS = ['AR_CREDIT_INVOICES']
ADVISORY_LOCK_ID = 777777

# Fecha de corte para stock.move / stock.inventory (antes hardcodeada).
# Configurable en backend/.env sin tocar código.
STOCK_DATE_FROM = os.environ.get('ODOO_STOCK_DATE_FROM', '2026-01-01')

# ══════════════════════════════════════════════════════════════════════
#  DE QUÉ ODOO SE LEE
#
#  El negocio se muda del Odoo 10 al 19. Durante la transición hace falta
#  poder apuntar a uno o al otro sin cambiar código, así que la fuente se
#  elige por variable de entorno:
#
#      ODOO_SOURCE_VERSION=10   (por defecto)  → como siempre
#      ODOO_SOURCE_VERSION=19                  → lee del Odoo 19
#
#  ⚠️  Antes de poner 19 hay que tener publicado el puente de ids
#      (repo Odoo: scripts/puente_ids.py). El mismo número significa
#      personas distintas en cada sistema —el cliente 538 es MEZA RAMOS
#      ELENA en el 10 y COTRINA LOPEZ EDUAR en el 19— así que escribir sin
#      traducir mezcla la historia de 8 años SIN dar ningún error.
#
#  Con la versión 19 no se le piden campos sueltos: el propio Odoo devuelve
#  las filas con la forma del espejo y los ids ya traducidos, con
#  pos.order.textil_exportar_para_espejo(). La lógica vive allá, al lado de
#  los datos, y acá solo se insertan.
# ══════════════════════════════════════════════════════════════════════
ODOO_SOURCE_VERSION = os.environ.get('ODOO_SOURCE_VERSION', '10').strip()
LEE_DEL_19 = ODOO_SOURCE_VERSION == '19'
# El Odoo 19 puede estar en otra dirección (otro server, otro puerto).
# Si no se define, se usa la misma conexión de siempre.
ODOO19_URL = os.environ.get('ODOO19_URL') or os.environ.get('ODOO_URL', '')
ODOO19_DB = os.environ.get('ODOO19_DB') or os.environ.get('ODOO_DB', '')
ODOO19_USER = os.environ.get('ODOO19_USER', '')
ODOO19_PASSWORD = os.environ.get('ODOO19_PASSWORD', '')


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



def nid(val):
    """False/0/'' -> None (NULL en Postgres). El exportador del Odoo 19 manda
    False para 'vacío' porque XML-RPC no sabe transmitir None; las columnas de
    id del espejo son integer y necesitan NULL, no un booleano."""
    return int(val) if val else None

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
        if mode and mode.upper() == 'INCREMENTAL' and cursor:
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

    def _update_cursor(self, job_code, company_key, cursor, ok=True, error=None):
        """Actualiza cursor por (job_code, company_key) en sync_job_cursor.
        También sigue actualizando sync_job (last_run_at, last_error) para
        compatibilidad con queries de status del frontend Ventas — ese campo
        se mantiene como "última corrida de cualquier empresa".

        BUG HISTÓRICO: antes el cursor vivía solo en sync_job indexado por
        job_code, así que cuando Ambission terminaba primero, sobrescribía
        el cursor con 'ahora' y ProyectoModa al correr después creía que
        ya estaba al día (cursor > sus write_dates pendientes). Por eso
        ProyectoModa quedaba siempre atrasado y había que forzarle FULL.
        El cursor por (job_code, company_key) elimina la dependencia entre
        empresas.
        """
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                if ok:
                    # 1) Cursor por empresa (la fuente de verdad ahora)
                    cur.execute("""
                        INSERT INTO odoo.sync_job_cursor (job_code, company_key, last_cursor, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (job_code, company_key)
                        DO UPDATE SET last_cursor = EXCLUDED.last_cursor, updated_at = NOW()
                    """, (job_code, company_key, cursor))
                    # 2) Metadata global del job (para frontend Ventas que muestra
                    #    "última corrida hace X min"). Mantenemos last_cursor también
                    #    para no romper queries legacy; no se usa para incremental.
                    cur.execute("""UPDATE odoo.sync_job SET last_run_at=now(), last_success_at=now(),
                                   last_cursor=%s, last_error=NULL WHERE job_code=%s""",
                                (cursor, job_code))
                else:
                    cur.execute("""UPDATE odoo.sync_job SET last_run_at=now(), last_error=%s
                                   WHERE job_code=%s""", (str(error)[:500] if error else None, job_code))
        finally:
            conn.close()

    def _refresh_matview_safe(self, mv_name: str):
        """Refresca una matview (intenta CONCURRENTLY primero, sino simple).
        No bloquea ni propaga errores — solo loguea. Pensado para correr
        después de jobs que mueven stock (STOCK_QUANTS / STOCK_MOVE) para
        mantener actualizadas las matviews dependientes como
        produccion.mv_stock_quant_resumen (que alimenta /reporte-stock).
        """
        try:
            conn = self._conn()
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    try:
                        cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
                        logger.info(f"  REFRESH CONCURRENTLY {mv_name} OK")
                    except Exception as e_conc:
                        # CONCURRENTLY requiere UNIQUE INDEX; si falta, fallback simple
                        logger.warning(f"  REFRESH CONCURRENTLY {mv_name} falló ({e_conc}), reintentando simple")
                        cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
                        logger.info(f"  REFRESH simple {mv_name} OK")
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"  REFRESH {mv_name} falló (no bloquea sync): {e}")

    def _get_cursor(self, job_code, company_key):
        """Lee cursor por (job_code, company_key). Si no existe la fila
        (job nuevo o empresa nueva), devuelve None — equivalente a FULL.
        El INSERT en _update_cursor crea la fila al primer run exitoso.
        """
        conn = self._conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT last_cursor FROM odoo.sync_job_cursor
                               WHERE job_code=%s AND company_key=%s""",
                            (job_code, company_key))
                r = cur.fetchone()
                return r[0] if r else None
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
                    # El lock está tomado. Verificar si está "atascado" —
                    # ocurre cuando un sync anterior se cortó sin liberar el lock
                    # (ej. thread muerto sin llegar al finally).
                    #
                    # OJO: la conexión que sostiene el lock queda OCIOSA durante
                    # todo el sync (los handlers abren sus propias conexiones),
                    # así que su query_start es viejo POR DISEÑO y no distingue
                    # un sync legítimo largo (STOCK_QUANTS puede tardar >1h) de
                    # un zombie. Antes solo se miraba query_start > 5 min y eso
                    # mataba syncs legítimos → quedaban DOS syncs concurrentes.
                    #
                    # Criterio nuevo: zombie = lock viejo (>5 min) Y ningún job
                    # con status RUNNING en sync_run_log. Todo sync real inserta
                    # una fila RUNNING al arrancar cada job; lock sin RUNNING =
                    # el proceso que lo tomó ya no está trabajando.
                    cur.execute("""
                        SELECT pl.pid, EXTRACT(EPOCH FROM (NOW() - pa.query_start))::int
                        FROM pg_locks pl
                        JOIN pg_stat_activity pa USING (pid)
                        WHERE pl.locktype = 'advisory'
                          AND pl.objid = %s
                          AND pl.granted = true
                        LIMIT 1
                    """, (ADVISORY_LOCK_ID,))
                    row = cur.fetchone()
                    cur.execute("SELECT EXISTS(SELECT 1 FROM odoo.sync_run_log WHERE status='RUNNING')")
                    sync_in_progress = cur.fetchone()[0]
                    if row and row[1] is not None and row[1] > 300 and not sync_in_progress:
                        zombie_pid, age_secs = row[0], row[1]
                        logger.warning(
                            f"Lock zombie detectado: PID {zombie_pid} con lock "
                            f"hace {age_secs}s. Matando conexión y reintentando."
                        )
                        cur.execute("SELECT pg_terminate_backend(%s)", (zombie_pid,))
                        # Reintentar tomar el lock tras matar al zombie
                        cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
                        if not cur.fetchone()[0]:
                            conn.close()
                            return {"success": False, "message": "Otra sincronización en curso.", "results": []}
                        # Lock recuperado, continuar con el sync
                    else:
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

            # Refrescar materialized views si se sincronizaron productos/atributos
            # (caches usados por reportes de stock — bajan queries de 14s a 2.5s)
            jobs_que_afectan_mv = {'PRODUCTS', 'ATTRIBUTES'}
            if any(r.get('job_code') in jobs_que_afectan_mv for r in results):
                try:
                    with conn.cursor() as cur:
                        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY odoo.mv_product_variant_flat;")
                        logger.info("Refreshed mv_product_variant_flat after PRODUCTS/ATTRIBUTES sync")
                except Exception as e:
                    logger.warning(f"No se pudo refrescar mv_product_variant_flat: {e}")

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
            # Cursor por (job_code, company_key): cada empresa avanza
            # independiente. Antes era solo por job_code, lo que causaba
            # que Ambission "robara" el cursor a ProyectoModa.
            cursor = self._get_cursor(jc, ck) if mode and mode.upper() == 'INCREMENTAL' else None
            handlers = {
                'RES_COMPANY': self._sync_res_company,
                'RES_USERS': self._sync_res_users,
                'RES_PARTNER': self._sync_res_partner,
                'X_LINEA_NEGOCIO': self._sync_x_linea_negocio,
                'PRODUCTS': self._sync_products,
                'ATTRIBUTES': self._sync_attributes,
                'STOCK_LOCATIONS': self._sync_stock_locations,
                'STOCK_QUANTS': self._sync_stock_quants,
                'STOCK_INVENTORY': self._sync_stock_inventory,
                'STOCK_MOVE': self._sync_stock_move,
                'POS_ORDERS': (self._sync_pos_orders_v19 if LEE_DEL_19
                               else self._sync_pos_orders),
                'AR_CREDIT_INVOICES': self._sync_credit_invoices,
            }
            h = handlers[jc]
            if jc in POS_JOBS or jc in MULTI_JOBS:
                rows, new_cursor = h(ck, mode, cursor, cs)
            else:
                rows, new_cursor = h(mode, cursor, cs)
            self._finish_log(log_id, 'OK', rows=rows)
            self._update_cursor(jc, ck, new_cursor or cursor, ok=True)
            logger.info(f"Sync OK: {jc}/{ck} -> {rows} rows")

            # Refrescar matviews dependientes después de jobs que mueven
            # stock. Sin esto, /reporte-stock muestra datos viejos hasta
            # el próximo refresh manual / nightly. Falla silenciosa para
            # no bloquear el sync principal.
            if jc in ('STOCK_QUANTS', 'STOCK_MOVE') and rows > 0:
                self._refresh_matview_safe('produccion.mv_stock_quant_resumen')

            return {"job_code": jc, "company_key": ck, "status": "OK", "rows": rows}
        except Exception as e:
            logger.error(f"Sync ERROR: {jc}/{ck}: {e}", exc_info=True)
            self._finish_log(log_id, 'ERROR', error=str(e))
            self._update_cursor(jc, ck, None, ok=False, error=e)
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

        # En mode FULL capturamos el timestamp ANTES de empezar para detectar
        # quants huérfanos al final. Un huérfano = fila local cuyo `synced_at`
        # quedó atrás del timestamp inicial = no apareció en este FULL = ya no
        # existe en Odoo. En INCREMENTAL no aplica porque solo trae deltas.
        from datetime import datetime, timezone
        sync_start_ts = datetime.now(timezone.utc) if (mode or '').upper() == 'FULL' else None
        if sync_start_ts:
            logger.info(f"  stock.quant FULL sync — start_ts={sync_start_ts.isoformat()} (huérfanos previos se borrarán al final)")

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

        # En mode FULL: borrar quants huérfanos (los que ya no existen en Odoo
        # pero quedaron en la copia local porque el INCREMENTAL no captura
        # deletes). Detectamos por synced_at < sync_start_ts (no se tocaron
        # durante este FULL, así que no aparecieron en Odoo).
        if sync_start_ts:
            conn = self._conn()
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM odoo.stock_quant "
                        "WHERE company_key='GLOBAL' AND synced_at < %s",
                        (sync_start_ts,),
                    )
                    deleted = cur.rowcount
                if deleted > 0:
                    logger.info(f"  stock.quant cleanup: {deleted} huérfanos eliminados (ya no existen en Odoo)")
                else:
                    logger.info(f"  stock.quant cleanup: 0 huérfanos (DB local en sync con Odoo)")
            except Exception as e:
                logger.error(f"  stock.quant cleanup ERROR: {e}", exc_info=True)
            finally:
                conn.close()

        return total_rows, max_w

    def _sync_stock_inventory(self, mode, cursor, cs):
        """Sync stock.inventory desde 2026-01-01 para ambas compañías."""
        total = 0
        max_w = cursor
        # Si una empresa falla, NO avanzamos el cursor: si no, los registros
        # pendientes de esa empresa quedan saltados para siempre (mismo bug
        # histórico de POS, versión "cursor compartido dentro de un job").
        all_companies_ok = True
        for ck in ('Ambission', 'ProyectoModa'):
            try:
                uid, pw = self._auth(ck)
            except Exception as e:
                logger.warning(f"stock.inventory skip {ck}: {e} — cursor NO avanzará")
                all_companies_ok = False
                continue
            base = [('date', '>=', STOCK_DATE_FROM)]
            domain = self._inc_domain(base, cursor, mode)
            fields = ['id', 'name', 'date', 'state', 'company_id',
                       'x_es_ingreso_produccion', 'location_id',
                       'create_uid', 'write_date']
            recs = self._paginate(uid, pw, 'stock.inventory', domain, fields, cs)
            vals = [
                (ck, r['id'], xtxt(r.get('name')), xdt(r.get('date')),
                 xtxt(r.get('state')), xid(r.get('company_id')),
                 xbool_nullable(r.get('x_es_ingreso_produccion')),
                 xid(r.get('location_id')), xid(r.get('create_uid')),
                 xdt(r.get('write_date')))
                for r in recs
            ]
            sql = """INSERT INTO odoo.stock_inventory (company_key,odoo_id,name,date,state,company_id,
                     x_es_ingreso_produccion,location_id,odoo_create_uid,odoo_write_date,synced_at)
                     VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                     name=EXCLUDED.name,date=EXCLUDED.date,state=EXCLUDED.state,company_id=EXCLUDED.company_id,
                     x_es_ingreso_produccion=EXCLUDED.x_es_ingreso_produccion,location_id=EXCLUDED.location_id,
                     odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
            template = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
            n = self._batch_exec(sql, template, vals)
            total += n
            max_w = self._max_wd(recs, max_w)
            logger.info(f"  stock.inventory {ck}: {n} rows")
        return total, (max_w if all_companies_ok else cursor)

    def _sync_stock_move(self, mode, cursor, cs):
        """Sync stock.move desde 2026-01-01 para ambas compañías."""
        total = 0
        max_w = cursor
        # Ver nota en _sync_stock_inventory: no avanzar cursor si una empresa falló.
        all_companies_ok = True

        # Mismo mecanismo que stock.quant: en FULL marcamos el instante de
        # arranque para poder borrar los huérfanos al final. Un movimiento
        # BORRADO en Odoo (típico: se arma un borrador de transferencia y se
        # elimina sin despachar) nunca vuelve a aparecer, y el INCREMENTAL no
        # tiene forma de enterarse — se queda congelado con su último estado.
        # Si ese estado era 'assigned', el modo Proyectado del reporte de stock
        # lo sigue descontando para siempre.
        #   caso real 2026-08: 18 movimientos de MORTAIN GM209→TALLER borrados
        #   el 14/08 seguían restando 19 unidades del proyectado de GM209.
        from datetime import datetime, timezone
        sync_start_ts = datetime.now(timezone.utc) if (mode or '').upper() == 'FULL' else None
        if sync_start_ts:
            logger.info(f"  stock.move FULL sync — start_ts={sync_start_ts.isoformat()} (huérfanos previos se borrarán al final)")
        for ck in ('Ambission', 'ProyectoModa'):
            try:
                uid, pw = self._auth(ck)
            except Exception as e:
                logger.warning(f"stock.move skip {ck}: {e} — cursor NO avanzará")
                all_companies_ok = False
                continue
            base = [('date', '>=', STOCK_DATE_FROM + ' 00:00:00')]
            domain = self._inc_domain(base, cursor, mode)
            fields = ['id', 'origin', 'product_id', 'product_tmpl_id',
                       'product_qty', 'company_id', 'date',
                       'location_id', 'location_dest_id', 'state',
                       'name', 'inventory_id', 'write_date']
            last_id = 0
            while True:
                page_domain = domain + [('id', '>', last_id)]
                batch = self.client.search_read(self.odoo_db, uid, pw, 'stock.move',
                                                page_domain, fields, limit=cs, offset=0, order='id asc')
                if not batch:
                    break
                last_id = max(r['id'] for r in batch)
                logger.info(f"  stock.move {ck} batch: {len(batch)} (last_id={last_id})")
                vals = [
                    (ck, r['id'], xtxt(r.get('origin')),
                     xid(r.get('product_id')), xid(r.get('product_tmpl_id')),
                     xnum(r.get('product_qty')),
                     xid(r.get('company_id')),
                     xdt(r.get('date')), xid(r.get('location_id')),
                     xid(r.get('location_dest_id')), xtxt(r.get('state')),
                     xtxt(r.get('name')), xid(r.get('inventory_id')),
                     xdt(r.get('write_date')))
                    for r in batch
                ]
                sql = """INSERT INTO odoo.stock_move (company_key,odoo_id,origin,product_id,product_tmpl_id,
                         product_qty,company_id,date,location_id,location_dest_id,state,name,inventory_id,
                         odoo_write_date,synced_at)
                         VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                         origin=EXCLUDED.origin,product_id=EXCLUDED.product_id,product_tmpl_id=EXCLUDED.product_tmpl_id,
                         product_qty=EXCLUDED.product_qty,
                         company_id=EXCLUDED.company_id,date=EXCLUDED.date,
                         location_id=EXCLUDED.location_id,location_dest_id=EXCLUDED.location_dest_id,
                         state=EXCLUDED.state,name=EXCLUDED.name,inventory_id=EXCLUDED.inventory_id,
                         odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
                template = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
                n = self._batch_exec(sql, template, vals)
                total += n
                max_w = self._max_wd(batch, max_w)
                if len(batch) < cs:
                    break
            logger.info(f"  stock.move {ck} total: {total}")

        # ── Barrido de pendientes: corre SIEMPRE, también en incremental ──
        # En Odoo un movimiento validado (state='done') NO se puede borrar: es
        # un asiento de inventario. Solo desaparecen los que están en borrador
        # o reservados — típicamente al eliminar un picking sin despachar.
        # Entonces no hace falta releer los ~260k movimientos para detectar
        # borrados: alcanza con preguntar por los pendientes locales (~660) y
        # ver cuáles ya no existen. Es una sola llamada y tarda segundos, así
        # que puede correr en cada sync en vez de esperar al FULL semanal.
        if all_companies_ok:
            self._barrer_pendientes_borrados()

        # Limpieza de huérfanos. DOS candados, ambos necesarios:
        #  1. solo en FULL — el INCREMENTAL trae deltas, así que casi todo
        #     quedaría "sin tocar" y borraríamos la tabla entera.
        #  2. solo si las DOS empresas se leyeron bien — si el auth de una
        #     falló, sus filas no se refrescaron y las estaríamos borrando.
        # Y el DELETE se acota a date >= STOCK_DATE_FROM porque el FULL solo
        # pide movimientos desde esa fecha: lo anterior nunca se refresca y
        # borrarlo sería destruir historia válida.
        if sync_start_ts and all_companies_ok:
            conn = self._conn()
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM odoo.stock_move "
                        "WHERE date >= %s AND synced_at < %s",
                        (STOCK_DATE_FROM + ' 00:00:00', sync_start_ts),
                    )
                    deleted = cur.rowcount
                if deleted > 0:
                    logger.info(f"  stock.move cleanup: {deleted} huérfanos eliminados (ya no existen en Odoo)")
                else:
                    logger.info(f"  stock.move cleanup: 0 huérfanos (DB local en sync con Odoo)")
            except Exception as e:
                logger.error(f"  stock.move cleanup ERROR: {e}", exc_info=True)
            finally:
                conn.close()
        elif sync_start_ts and not all_companies_ok:
            logger.warning("  stock.move cleanup OMITIDO: una empresa falló, "
                           "borrar ahora eliminaría filas válidas no refrescadas")

        return total, (max_w if all_companies_ok else cursor)

    def _barrer_pendientes_borrados(self):
        """Borra los movimientos PENDIENTES locales que ya no existen en Odoo.

        Barato por diseño: solo mira los que están en un estado borrable
        (draft/waiting/confirmed/partially_available/assigned). Los 'done' y
        'cancel' no se pueden eliminar en Odoo, así que no hace falta
        revisarlos — y son el 99.7% de la tabla.

        Se pregunta a Odoo por esos ids concretos y se borra lo que no vuelva.
        Solo se elimina lo que se confirmó ausente: si la llamada falla, no se
        borra nada.
        """
        PEND = ('draft', 'waiting', 'confirmed', 'partially_available', 'assigned')
        try:
            conn = self._conn()
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT company_key, odoo_id FROM odoo.stock_move "
                        "WHERE state = ANY(%s)", (list(PEND),))
                    locales = cur.fetchall()
            finally:
                conn.close()
            if not locales:
                return

            por_empresa = {}
            for ck, oid in locales:
                por_empresa.setdefault(ck, []).append(oid)

            total_borrados = 0
            for ck, ids in por_empresa.items():
                try:
                    uid, pw = self._auth(ck)
                except Exception as e:
                    logger.warning(f"  barrido pendientes: skip {ck} ({e})")
                    continue
                # Se pregunta en tandas por si la lista crece.
                vivos = set()
                for i in range(0, len(ids), 2000):
                    lote = ids[i:i + 2000]
                    res = self.client.search_read(
                        self.odoo_db, uid, pw, 'stock.move',
                        [('id', 'in', lote)], ['id'], limit=0)
                    vivos.update(r['id'] for r in res)
                muertos = [i for i in ids if i not in vivos]
                if not muertos:
                    continue
                conn = self._conn()
                conn.autocommit = True
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM odoo.stock_move "
                            "WHERE company_key = %s AND odoo_id = ANY(%s)",
                            (ck, muertos))
                        total_borrados += cur.rowcount
                finally:
                    conn.close()
                logger.info(f"  barrido pendientes {ck}: {len(muertos)} borrados en Odoo, eliminados de la copia")
            if total_borrados == 0:
                logger.info(f"  barrido pendientes: 0 fantasmas ({len(locales)} pendientes revisados)")
        except Exception as e:
            logger.error(f"  barrido pendientes ERROR: {e}", exc_info=True)

    def _sync_res_users(self, mode, cursor, cs):
        """Sync res.users from all companies (Ambission + ProyectoModa)."""
        total = 0
        max_w = cursor
        # Ver nota en _sync_stock_inventory: no avanzar cursor si una empresa falló.
        all_companies_ok = True
        for ck in ('Ambission', 'ProyectoModa'):
            try:
                uid, pw = self._auth(ck)
            except Exception as e:
                logger.warning(f"res.users skip {ck}: {e} — cursor NO avanzará")
                all_companies_ok = False
                continue
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
            total += n
            max_w = self._max_wd(recs, max_w)
            logger.info(f"  res.users from {ck}: {n} rows")
        return total, (max_w if all_companies_ok else cursor)

    def _sync_res_partner(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        # D5: UBIGEO completo + zip + street2.
        # state_id ahora se guarda como FK + nombre (antes solo nombre).
        fields = ['id','name','display_name','parent_id','commercial_partner_id',
                   'x_cliente_principal','x_es_principal','mayorista','x_no_llamar','x_ultima_venta',
                   'vat','phone','mobile','street','street2','city','zip',
                   'country_id','state_id','province_id','district_id','active',
                   'catalog_06_id',
                   'create_date','create_uid','write_date','write_uid']
        recs = self._paginate(uid, pw, 'res.partner', domain, fields, cs)
        vals = [
            (r['id'], xtxt(r.get('name')), xtxt(r.get('display_name')),
             xid(r.get('parent_id')), xid(r.get('commercial_partner_id')),
             xid(r.get('x_cliente_principal')), xbool_nullable(r.get('x_es_principal')),
             xbool_nullable(r.get('mayorista')), xbool_nullable(r.get('x_no_llamar')),
             xdt(r.get('x_ultima_venta')),
             xtxt(r.get('vat')), xtxt(r.get('phone')), xtxt(r.get('mobile')),
             xtxt(r.get('street')), xtxt(r.get('street2')),
             xtxt(r.get('city')), xtxt(r.get('zip')),
             # UBIGEO m2o → FK + nombre
             xid(r.get('country_id')),   xm2o_name(r.get('country_id')),
             xid(r.get('state_id')),     xm2o_name(r.get('state_id')),
             xid(r.get('province_id')),  xm2o_name(r.get('province_id')),
             xid(r.get('district_id')),  xm2o_name(r.get('district_id')),
             xbool(r.get('active')),
             # D7) Tipo doc (catalog_06): m2o → FK + nombre (RUC/DNI/CE/Pas)
             xid(r.get('catalog_06_id')), xm2o_name(r.get('catalog_06_id')),
             xdt(r.get('write_date')), xdt(r.get('create_date')),
             xid(r.get('create_uid')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.res_partner (company_key,odoo_id,name,display_name,parent_id,commercial_partner_id,
                 x_cliente_principal,x_es_principal,mayorista,x_no_llamar,x_ultima_venta,
                 vat,phone,mobile,street,street2,city,zip,
                 country_id,country_name,state_id,state_name,
                 province_id,province_name,district_id,district_name,
                 active,
                 catalog_06_id,catalog_06_name,
                 odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,display_name=EXCLUDED.display_name,parent_id=EXCLUDED.parent_id,
                 commercial_partner_id=EXCLUDED.commercial_partner_id,
                 x_cliente_principal=EXCLUDED.x_cliente_principal,x_es_principal=EXCLUDED.x_es_principal,
                 mayorista=EXCLUDED.mayorista,x_no_llamar=EXCLUDED.x_no_llamar,
                 x_ultima_venta=EXCLUDED.x_ultima_venta,
                 vat=EXCLUDED.vat,phone=EXCLUDED.phone,mobile=EXCLUDED.mobile,
                 street=EXCLUDED.street,street2=EXCLUDED.street2,
                 city=EXCLUDED.city,zip=EXCLUDED.zip,
                 country_id=EXCLUDED.country_id,country_name=EXCLUDED.country_name,
                 state_id=EXCLUDED.state_id,state_name=EXCLUDED.state_name,
                 province_id=EXCLUDED.province_id,province_name=EXCLUDED.province_name,
                 district_id=EXCLUDED.district_id,district_name=EXCLUDED.district_name,
                 active=EXCLUDED.active,
                 catalog_06_id=EXCLUDED.catalog_06_id,catalog_06_name=EXCLUDED.catalog_06_name,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,
                 synced_at=now()"""
        # 32 %s = id + 31 campos (2 nuevos D7: catalog_06_id, catalog_06_name)
        template = "('GLOBAL'," + ",".join(["%s"] * 32) + ",now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_x_linea_negocio(self, mode, cursor, cs):
        """Sync x_linea_negocio master table."""
        uid, pw = self._auth('Ambission')
        domain = self._inc_domain([], cursor, mode)
        fields = ['id', 'x_name', 'create_date', 'create_uid', 'write_date', 'write_uid']
        recs = self._paginate(uid, pw, 'x_linea_negocio', domain, fields, cs)
        vals = [
            (r['id'], xtxt(r.get('x_name')),
             xdt(r.get('create_date')), xid(r.get('create_uid')),
             xdt(r.get('write_date')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.x_linea_negocio (company_key,odoo_id,name,
                 odoo_create_date,odoo_create_uid,odoo_write_date,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,
                 odoo_create_date=EXCLUDED.odoo_create_date,odoo_create_uid=EXCLUDED.odoo_create_uid,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        template = "('GLOBAL',%s,%s,%s,%s,%s,%s,now())"
        n = self._batch_exec(sql, template, vals)
        return n, self._max_wd(recs, cursor)

    def _sync_products(self, mode, cursor, cs):
        uid, pw = self._auth('Ambission')

        # Include archived products and products that are both sale+purchase
        base = [('sale_ok','=',True)]
        domain = self._inc_domain(base, cursor, mode)
        ctx_no_active = {'active_test': False}
        # x_marca is char; x_tipo is many2one; tela/entalle/hilo/articulo are many2one
        tmpl_fields = ['id','name','active','sale_ok','purchase_ok','list_price',
                        'x_marca','x_tipo','tela','entalle','hilo','articulo','x_linea_negocio_id',
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
             # <campo>         = valor tal cual está en el producto en Odoo
             # <campo>_resumen = agrupación del catálogo (product.tipo.x_tipo_resumen,
             #                   product.tela.x_tela, product.entalle.x_entalle)
             xm2o_name(r.get('x_tipo')),
             _resolve(r.get('x_tipo'), tipo_map),
             xm2o_name(r.get('tela')),
             _resolve(r.get('tela'), tela_map),
             xm2o_name(r.get('entalle')),
             _resolve(r.get('entalle'), entalle_map),
             xm2o_name(r.get('articulo')),      # product.articulo (many2one)
             xm2o_name(r.get('hilo')),
             xid(r.get('x_linea_negocio_id')),
             xm2o_name(r.get('x_linea_negocio_id')),
             xdt(r.get('write_date')), xdt(r.get('create_date')),
             xid(r.get('create_uid')), xid(r.get('write_uid')))
            for r in recs
        ]
        sql = """INSERT INTO odoo.product_template (company_key,odoo_id,name,active,sale_ok,purchase_ok,list_price,
                 marca,tipo,tipo_resumen,tela,tela_resumen,entalle,entalle_resumen,articulo,hilo,linea_negocio_id,linea_negocio,odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                 VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                 name=EXCLUDED.name,active=EXCLUDED.active,sale_ok=EXCLUDED.sale_ok,purchase_ok=EXCLUDED.purchase_ok,
                 list_price=EXCLUDED.list_price,marca=EXCLUDED.marca,tipo=EXCLUDED.tipo,tipo_resumen=EXCLUDED.tipo_resumen,
                 tela=EXCLUDED.tela,tela_resumen=EXCLUDED.tela_resumen,
                 entalle=EXCLUDED.entalle,entalle_resumen=EXCLUDED.entalle_resumen,articulo=EXCLUDED.articulo,hilo=EXCLUDED.hilo,
                 linea_negocio_id=EXCLUDED.linea_negocio_id,linea_negocio=EXCLUDED.linea_negocio,
                 odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                 odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
        tmpl_template = "('GLOBAL',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())"
        tmpl_rows = self._batch_exec(sql, tmpl_template, vals)

        # La agrupación vive en el catálogo, no en el producto: recalcular siempre
        # (si no, editar product.tipo/tela/entalle en Odoo nunca se reflejaría).
        self._refresh_resumen('tipo', tipo_map)
        self._refresh_resumen('tela', tela_map)
        self._refresh_resumen('entalle', entalle_map)
        max_w = self._max_wd(recs, cursor)

        # B) product.product
        tmpl_ids = [r['id'] for r in recs]
        pp_rows = 0
        rel_rows = 0
        # Dominio de variantes:
        # - variantes de templates modificados, Y ADEMÁS
        # - en INCREMENTAL, variantes modificadas directamente (ej. barcode
        #   editado) aunque su template no cambió — antes se perdían hasta
        #   correr un FULL, porque editar la variante no toca el write_date
        #   del template.
        cursor_str = cursor.strftime('%Y-%m-%d %H:%M:%S') if cursor else None
        if tmpl_ids and cursor_str:
            pp_domain = ['|', ('product_tmpl_id', 'in', tmpl_ids),
                         ('write_date', '>', cursor_str)]
        elif tmpl_ids:
            pp_domain = [('product_tmpl_id', 'in', tmpl_ids)]
        elif cursor_str:
            pp_domain = [('write_date', '>', cursor_str)]
        else:
            pp_domain = None
        if pp_domain is not None:
            pp_fields = ['id','product_tmpl_id','barcode','active',
                         'attribute_value_ids','create_date','create_uid','write_date','write_uid']
            try:
                variants = self._paginate(uid, pw, 'product.product', pp_domain, pp_fields, cs, ctx=ctx_no_active)
            except Exception:
                pp_fields.remove('attribute_value_ids')
                variants = self._paginate(uid, pw, 'product.product', pp_domain, pp_fields, cs, ctx=ctx_no_active)

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

        # NOTA (UX): el conteo reportado en sync_run_log.rows_upserted ya NO
        # incluye `rel_rows` (las filas de product_attribute_value_product_product_rel
        # que sólo registran "este variant tiene esta talla/color/hilo"). Esas
        # relaciones se siguen sincronizando — solo no se cuentan para que el
        # número que ve el usuario en el modal de Estado de Sincronización
        # corresponda a productos reales (templates + variants), no a
        # asociaciones internas que inflan el conteo a ~3× sin agregar
        # información útil al operador.
        logger.info(f"  PRODUCTS detalle: {tmpl_rows} templates + {pp_rows} variants + {rel_rows} rels (rels no contadas)")
        return tmpl_rows + pp_rows, max_w

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

    def _sync_pos_orders(self, ck, mode, cursor, cs, date_from=None, date_to=None):
        uid, pw = self._auth(ck)
        ctx, cid = self._company_ctx(ck)
        base = [('company_id', '=', cid)] if cid else []
        if date_from:
            base.append(('date_order', '>=', date_from + ' 00:00:00'))
        if date_to:
            base.append(('date_order', '<=', date_to + ' 23:59:59'))
        domain = self._inc_domain(base, cursor, mode)

        order_fields = ['id', 'name', 'date_order', 'partner_id', 'user_id', 'vendedor_id',
                        'amount_total', 'amount_tax', 'state',
                        'is_cancel', 'order_cancel', 'x_cliente_principal', 'reserva', 'reserva_use_id',
                        'location_id', 'company_id',
                        'tipo_comp', 'num_comp', 'x_pagos',
                        'create_date', 'create_uid', 'write_date', 'write_uid']

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
                     xid(r.get('partner_id')), xid(r.get('user_id')), xid(r.get('vendedor_id')),
                     xnum(r.get('amount_total')), xnum(r.get('amount_tax')),
                     xtxt(r.get('state')),
                     xbool_nullable(r.get('is_cancel')), xbool_nullable(r.get('order_cancel')),
                     xid(r.get('x_cliente_principal')), xbool_nullable(r.get('reserva')),
                     xid(r.get('reserva_use_id')),
                     xid(r.get('location_id')), xid(r.get('company_id')),
                     xtxt(r.get('tipo_comp')), xtxt(r.get('num_comp')), xtxt(r.get('x_pagos')),
                     xdt(r.get('write_date')), xdt(r.get('create_date')),
                     xid(r.get('create_uid')), xid(r.get('write_uid')))
                    for r in orders
                ]
                o_sql = """INSERT INTO odoo.pos_order (company_key,odoo_id,name,date_order,partner_id,user_id,vendedor_id,
                           amount_total,amount_tax,state,is_cancel,order_cancel,
                           x_cliente_principal,reserva,reserva_use_id,location_id,company_id,
                           tipo_comp,num_comp,x_pagos,
                           odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                           VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                           name=EXCLUDED.name,date_order=EXCLUDED.date_order,partner_id=EXCLUDED.partner_id,
                           user_id=EXCLUDED.user_id,vendedor_id=EXCLUDED.vendedor_id,
                           amount_total=EXCLUDED.amount_total,amount_tax=EXCLUDED.amount_tax,
                           state=EXCLUDED.state,is_cancel=EXCLUDED.is_cancel,order_cancel=EXCLUDED.order_cancel,
                           x_cliente_principal=EXCLUDED.x_cliente_principal,reserva=EXCLUDED.reserva,
                           reserva_use_id=EXCLUDED.reserva_use_id,location_id=EXCLUDED.location_id,
                           company_id=EXCLUDED.company_id,tipo_comp=EXCLUDED.tipo_comp,
                           num_comp=EXCLUDED.num_comp,x_pagos=EXCLUDED.x_pagos,
                           odoo_write_date=EXCLUDED.odoo_write_date,odoo_create_date=EXCLUDED.odoo_create_date,
                           odoo_create_uid=EXCLUDED.odoo_create_uid,odoo_write_uid=EXCLUDED.odoo_write_uid,synced_at=now()"""
                total_orders += self._batch_exec(o_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", o_vals)
                max_w = self._max_wd(orders, max_w)

                # Lines for this batch
                oids = [r['id'] for r in orders]
                if oids:
                    lines = self._paginate(uid, pw, 'pos.order.line', [('order_id', 'in', oids)],
                                           ['id', 'order_id', 'product_id', 'qty', 'price_unit', 'discount',
                                            'price_subtotal', 'price_subtotal_incl', 'write_date'], cs)
                    l_vals = [
                        (ck, l['id'], xid(l.get('order_id')), xid(l.get('product_id')),
                         xnum(l.get('qty')), xnum(l.get('price_unit')),
                         xnum(l.get('discount')), xnum(l.get('price_subtotal')),
                         xnum(l.get('price_subtotal_incl')),
                         xdt(l.get('write_date')))
                        for l in lines
                    ]
                    # price_subtotal_incl: campo nativo de Odoo (qty × price_unit con descuento e IGV
                    # ya incluido y redondeado por Odoo). Evita los decimales raros de recalcular
                    # price_subtotal × 1.18 en SQL del lado nuestro.
                    l_sql = """INSERT INTO odoo.pos_order_line (company_key,odoo_id,order_id,product_id,qty,price_unit,
                               discount,price_subtotal,price_subtotal_incl,odoo_write_date,synced_at)
                               VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                               order_id=EXCLUDED.order_id,product_id=EXCLUDED.product_id,qty=EXCLUDED.qty,
                               price_unit=EXCLUDED.price_unit,discount=EXCLUDED.discount,
                               price_subtotal=EXCLUDED.price_subtotal,
                               price_subtotal_incl=EXCLUDED.price_subtotal_incl,
                               odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
                    total_lines += self._batch_exec(l_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", l_vals)

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

    def sync_pos_targeted(self, company_key, full=False, date_from=None, date_to=None):
        """Public method for targeted POS sync with detailed metrics."""
        import psycopg2
        conn = psycopg2.connect(self.pg_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Count before
        cur.execute("SELECT count(*) FROM odoo.pos_order WHERE company_key=%s", (company_key,))
        orders_before = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM odoo.pos_order_line WHERE company_key=%s", (company_key,))
        lines_before = cur.fetchone()[0]

        # Get chunk_size from sync_job
        cur.execute("SELECT chunk_size FROM odoo.sync_job WHERE job_code='POS_ORDERS'")
        row = cur.fetchone()
        cs = row[0] if row else 1000
        conn.close()

        mode = 'FULL' if full else 'INCREMENTAL'
        # Cursor por (job, empresa) — antes era solo por job y eso causaba
        # que Ambission y ProyectoModa se pisaran. Ahora cada una tiene
        # su propio cursor en sync_job_cursor.
        cursor = None if full else self._get_cursor('POS_ORDERS', company_key)

        total, max_w = self._sync_pos_orders(company_key, mode, cursor, cs,
                                              date_from=date_from, date_to=date_to)

        # Count after
        conn = psycopg2.connect(self.pg_url)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM odoo.pos_order WHERE company_key=%s", (company_key,))
        orders_after = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM odoo.pos_order_line WHERE company_key=%s", (company_key,))
        lines_after = cur.fetchone()[0]
        conn.close()

        inserted_orders = max(orders_after - orders_before, 0)
        inserted_lines = max(lines_after - lines_before, 0)
        updated_orders = max(total - inserted_orders - inserted_lines, 0)

        return {
            "inserted_orders": inserted_orders,
            "updated_orders": updated_orders,
            "inserted_lines": inserted_lines,
            "updated_lines": max(total - inserted_orders - updated_orders - inserted_lines, 0),
            "total_affected": total,
        }

    # ================================================================
    # CREDIT INVOICES (account.invoice con is_credit=True)
    # ================================================================

    def _sync_credit_invoices(self, ck, mode, cursor, cs):
        uid, pw = self._auth(ck)
        ctx, cid = self._company_ctx(ck)
        # Solo facturas NO PAGADAS: state='open'. Las pagadas (paid),
        # canceladas (cancel) o borrador (draft) no tienen saldo pendiente
        # y no necesitan estar en cobranzas — reduce volumen de sync.
        base = [
            ('is_credit', '=', True),
            ('type',      '=', 'out_invoice'),
            ('state',     '=', 'open'),
        ]
        if cid:
            base.append(('company_id', '=', cid))
        domain = self._inc_domain(base, cursor, mode)

        inv_fields = ['id', 'number', 'date_invoice', 'date_due', 'partner_id', 'user_id',
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
                     r.get('date_due')     if r.get('date_due')     else None,
                     xid(r.get('partner_id')), xid(r.get('user_id')),
                     xid(r.get('company_id')), xtxt(r.get('state')),
                     xnum(r.get('amount_total')), xnum(r.get('residual')),
                     xid(r.get('payment_term_id')), xid(r.get('currency_id')),
                     xdt(r.get('create_date')), xid(r.get('create_uid')),
                     xdt(r.get('write_date')), xid(r.get('write_uid')))
                    for r in invoices
                ]
                inv_sql = """INSERT INTO odoo.account_invoice_credit
                    (company_key, odoo_id, number, date_invoice, date_due, partner_id, user_id,
                     company_id, state, amount_total, amount_residual,
                     payment_term_id, currency_id,
                     odoo_create_date, odoo_create_uid, odoo_write_date, odoo_write_uid, synced_at)
                    VALUES %s ON CONFLICT (company_key, odoo_id) DO UPDATE SET
                     number=EXCLUDED.number, date_invoice=EXCLUDED.date_invoice,
                     date_due=EXCLUDED.date_due,
                     partner_id=EXCLUDED.partner_id, user_id=EXCLUDED.user_id,
                     company_id=EXCLUDED.company_id, state=EXCLUDED.state,
                     amount_total=EXCLUDED.amount_total, amount_residual=EXCLUDED.amount_residual,
                     payment_term_id=EXCLUDED.payment_term_id, currency_id=EXCLUDED.currency_id,
                     odoo_create_date=EXCLUDED.odoo_create_date, odoo_create_uid=EXCLUDED.odoo_create_uid,
                     odoo_write_date=EXCLUDED.odoo_write_date, odoo_write_uid=EXCLUDED.odoo_write_uid,
                     synced_at=now()"""
                total_inv += self._batch_exec(inv_sql,
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", inv_vals)
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

        # ── Auto-limpieza de zombis ──
        # Como filtramos por state='open', cuando una factura se PAGA en Odoo
        # ya no aparece en el sync incremental → queda zombi en nuestra DB.
        # Solución: preguntar a Odoo "de los IDs que tengo guardados, cuáles
        # ya NO son 'open'?" y borrar esos en una sola query.
        try:
            conn = self._conn()
            with conn.cursor() as cur:
                cur.execute("SELECT odoo_id FROM odoo.account_invoice_credit WHERE company_key = %s",
                            (ck,))
                local_ids = [r[0] for r in cur.fetchall()]

            if local_ids:
                # Batch en chunks de 5000 para evitar payload gigante en XMLRPC
                deleted = 0
                CHUNK = 5000
                for i in range(0, len(local_ids), CHUNK):
                    chunk = local_ids[i:i + CHUNK]
                    no_longer_open = self.client.search(
                        self.odoo_db, uid, pw, 'account.invoice',
                        [('id', 'in', chunk),
                         ('state', '!=', 'open')],
                        context=ctx,
                    )
                    if no_longer_open:
                        with conn.cursor() as cur:
                            # Borrar líneas primero (FK lógica)
                            cur.execute(
                                "DELETE FROM odoo.account_invoice_credit_line "
                                "WHERE company_key = %s AND invoice_id = ANY(%s)",
                                (ck, no_longer_open),
                            )
                            cur.execute(
                                "DELETE FROM odoo.account_invoice_credit "
                                "WHERE company_key = %s AND odoo_id = ANY(%s)",
                                (ck, no_longer_open),
                            )
                        conn.commit()
                        deleted += len(no_longer_open)
                if deleted > 0:
                    logger.info(f"  Credit inv cleanup: {deleted} facturas pagadas/canceladas removidas")
        except Exception as e:
            logger.warning(f"  Credit inv cleanup falló (no es crítico): {e}")

        return total_inv + total_lines, max_w


    # ══════════════════════════════════════════════════════════════════
    #  VENTAS · leyendo del ODOO 19
    #
    #  A diferencia del camino del Odoo 10, acá NO se piden campos sueltos.
    #  El Odoo 19 devuelve las filas ya con la forma del espejo y con los ids
    #  ya traducidos (ver pos_textil_migracion/models/pos_order_espejo.py del
    #  repo Odoo). Los motivos:
    #
    #   · Varios campos que el espejo espera son inventos del Odoo 10 y en el
    #     19 la información vive en otro lado (la tienda sale de la caja, el
    #     comprobante de otro campo, los pagos de una lista...). Esa traducción
    #     conviene tenerla junto a los datos, donde se puede probar y donde no
    #     se rompe cada vez que Odoo cambia algo.
    #
    #   · Los ids se pisan entre sistemas. Traducirlos acá significaría copiar
    #     y mantener el mapa del otro lado; pedirlos ya traducidos es una sola
    #     fuente de verdad.
    #
    #  El cursor es el ID de la última venta traída (no una fecha): así se
    #  avanza sin repetir ni saltear aunque dos ventas tengan la misma hora.
    # ══════════════════════════════════════════════════════════════════
    def _cliente_19(self):
        """Conexión al Odoo 19. Falla claro si no está configurada."""
        if not (ODOO19_URL and ODOO19_DB and ODOO19_USER and ODOO19_PASSWORD):
            raise RuntimeError(
                "ODOO_SOURCE_VERSION=19 pero falta la conexión al Odoo 19. "
                "Definí ODOO19_URL, ODOO19_DB, ODOO19_USER y ODOO19_PASSWORD "
                "en backend/.env")
        cli = OdooClient(ODOO19_URL)
        uid = cli.authenticate(ODOO19_DB, ODOO19_USER, ODOO19_PASSWORD)
        if not uid:
            raise RuntimeError(
                "El Odoo 19 rechazó el usuario %s (revisá ODOO19_USER y "
                "ODOO19_PASSWORD)" % ODOO19_USER)
        return cli, uid, ODOO19_PASSWORD

    def _sync_pos_orders_v19(self, ck, mode, cursor, cs):
        cli, uid, pw = self._cliente_19()

        # El cursor del 19 es un id. En una corrida completa se arranca de cero.
        try:
            desde = 0 if mode == 'full' else int(cursor or 0)
        except (TypeError, ValueError):
            # Si quedó guardado un cursor del Odoo 10 (una fecha), no sirve acá:
            # se arranca de cero antes que saltear ventas en silencio.
            logger.warning("  Cursor %r no es un id: arranco de cero.", cursor)
            desde = 0

        total_ordenes = total_lineas = 0
        ultimo = desde
        vueltas = 0

        while True:
            vueltas += 1
            if vueltas > 2000:            # red de seguridad contra bucle infinito
                logger.error("  Corté por exceso de vueltas (cursor %s)", ultimo)
                break

            res = cli.execute_kw(
                ODOO19_DB, uid, pw, 'pos.order', 'textil_exportar_para_espejo',
                [], {'desde_id': ultimo, 'limite': cs})
            ordenes = res.get('ordenes') or []
            lineas = res.get('lineas') or []
            if not ordenes:
                break

            o_vals = [
                (o['company_key'], o['odoo_id'], xtxt(o.get('name')), xdt(o.get('date_order')),
                 nid(o.get('partner_id')), nid(o.get('user_id')), nid(o.get('vendedor_id')),
                 xnum(o.get('amount_total')), xnum(o.get('amount_tax')),
                 xtxt(o.get('state')),
                 xbool_nullable(o.get('is_cancel')), xbool_nullable(o.get('order_cancel')),
                 nid(o.get('x_cliente_principal')), xbool_nullable(o.get('reserva')),
                 nid(o.get('reserva_use_id')),
                 nid(o.get('location_id')), nid(o.get('company_id')),
                 xtxt(o.get('tipo_comp')), xtxt(o.get('num_comp')), xtxt(o.get('x_pagos')),
                 xdt(o.get('odoo_write_date')), xdt(o.get('odoo_create_date')),
                 None, None)
                for o in ordenes
            ]
            o_sql = """INSERT INTO odoo.pos_order (company_key,odoo_id,name,date_order,partner_id,user_id,vendedor_id,
                       amount_total,amount_tax,state,is_cancel,order_cancel,
                       x_cliente_principal,reserva,reserva_use_id,location_id,company_id,
                       tipo_comp,num_comp,x_pagos,
                       odoo_write_date,odoo_create_date,odoo_create_uid,odoo_write_uid,synced_at)
                       VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                       name=EXCLUDED.name,date_order=EXCLUDED.date_order,
                       partner_id=EXCLUDED.partner_id,user_id=EXCLUDED.user_id,
                       vendedor_id=EXCLUDED.vendedor_id,amount_total=EXCLUDED.amount_total,
                       amount_tax=EXCLUDED.amount_tax,state=EXCLUDED.state,
                       is_cancel=EXCLUDED.is_cancel,order_cancel=EXCLUDED.order_cancel,
                       x_cliente_principal=EXCLUDED.x_cliente_principal,
                       reserva=EXCLUDED.reserva,reserva_use_id=EXCLUDED.reserva_use_id,
                       location_id=EXCLUDED.location_id,company_id=EXCLUDED.company_id,
                       tipo_comp=EXCLUDED.tipo_comp,num_comp=EXCLUDED.num_comp,
                       x_pagos=EXCLUDED.x_pagos,
                       odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
            total_ordenes += self._batch_exec(
                o_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())",
                o_vals)

            if lineas:
                l_vals = [
                    (l['company_key'], l['odoo_id'], l['order_id'], nid(l.get('product_id')),
                     xnum(l.get('qty')), xnum(l.get('price_unit')), xnum(l.get('discount')),
                     xnum(l.get('price_subtotal')), xnum(l.get('price_subtotal_incl')),
                     xdt(l.get('odoo_write_date')))
                    for l in lineas
                ]
                l_sql = """INSERT INTO odoo.pos_order_line (company_key,odoo_id,order_id,product_id,qty,price_unit,
                           discount,price_subtotal,price_subtotal_incl,odoo_write_date,synced_at)
                           VALUES %s ON CONFLICT (company_key,odoo_id) DO UPDATE SET
                           order_id=EXCLUDED.order_id,product_id=EXCLUDED.product_id,qty=EXCLUDED.qty,
                           price_unit=EXCLUDED.price_unit,discount=EXCLUDED.discount,
                           price_subtotal=EXCLUDED.price_subtotal,
                           price_subtotal_incl=EXCLUDED.price_subtotal_incl,
                           odoo_write_date=EXCLUDED.odoo_write_date,synced_at=now()"""
                total_lineas += self._batch_exec(
                    l_sql, "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())", l_vals)

            ultimo = res.get('ultimo_id') or ultimo
            if not res.get('hay_mas'):
                break
            time.sleep(0.2)               # sin apurar al servidor

        logger.info("  Odoo 19 · %s ventas y %s líneas (cursor %s)",
                    total_ordenes, total_lineas, ultimo)
        # El cursor se guarda como texto, igual que el del Odoo 10.
        return total_ordenes + total_lineas, str(ultimo)

    # ---- Batch exec helper ----

    def _refresh_resumen(self, field, name_map):
        """Reaplica la agrupación del catálogo a TODOS los productos.

        El sync incremental solo re-trae productos cuyo write_date cambió, pero la
        agrupación no vive en el producto sino en el catálogo (product.tipo,
        product.tela, product.entalle). Al editar el catálogo en Odoo, el write_date
        del producto NO cambia, así que <campo>_resumen se quedaba congelado con el
        valor viejo. Esto lo recalcula en cada sync.
        """
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                if name_map:
                    args = ','.join(cur.mogrify('(%s,%s)', (k, v)).decode()
                                    for k, v in name_map.items())
                    cur.execute(f"""
                        UPDATE odoo.product_template pt
                        SET {field}_resumen = COALESCE(m.resumen, pt.{field})
                        FROM (VALUES {args}) AS m(name, resumen)
                        WHERE pt.company_key = 'GLOBAL' AND pt.{field} = m.name
                          AND pt.{field}_resumen IS DISTINCT FROM COALESCE(m.resumen, pt.{field})
                    """)
                    changed = cur.rowcount
                    cur.execute(f"""
                        UPDATE odoo.product_template pt
                        SET {field}_resumen = pt.{field}
                        WHERE pt.company_key = 'GLOBAL' AND pt.{field} IS NOT NULL
                          AND pt.{field} NOT IN (SELECT name FROM (VALUES {args}) AS m(name, resumen))
                          AND pt.{field}_resumen IS DISTINCT FROM pt.{field}
                    """)
                    changed += cur.rowcount
                else:
                    cur.execute(f"""
                        UPDATE odoo.product_template pt
                        SET {field}_resumen = pt.{field}
                        WHERE pt.company_key = 'GLOBAL'
                          AND pt.{field}_resumen IS DISTINCT FROM pt.{field}
                    """)
                    changed = cur.rowcount
            conn.commit()
            if changed:
                logger.info(f"  {field}_resumen recalculado desde catálogo: {changed} filas")
            return changed
        except Exception as e:
            conn.rollback()
            logger.warning(f"  no se pudo recalcular {field}_resumen: {e}")
            return 0
        finally:
            conn.close()

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
