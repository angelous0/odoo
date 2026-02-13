from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from migration import MIGRATION_SQL, ODOO_TABLES, ODOO_VIEWS
from scheduler import SyncScheduler

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (kept for platform compatibility)
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# PostgreSQL connection
pg_url = os.environ['PG_URL']

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

scheduler = SyncScheduler()


@contextmanager
def get_pg_conn():
    conn = psycopg2.connect(pg_url)
    try:
        yield conn
    finally:
        conn.close()


def run_migration():
    """Execute the full migration SQL against PostgreSQL."""
    with get_pg_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(MIGRATION_SQL)
            conn.commit()
            logger.info("Migration completed successfully")
            return {"success": True, "message": "Migración ejecutada correctamente"}
        except Exception as e:
            conn.rollback()
            logger.error(f"Migration failed: {e}")
            return {"success": False, "message": str(e)}


# Auto-migrate on startup + start scheduler
@app.on_event("startup")
async def startup_event():
    try:
        result = run_migration()
        if result["success"]:
            logger.info("Auto-migration on startup: OK")
        else:
            logger.warning(f"Auto-migration on startup failed: {result['message']}")
    except Exception as e:
        logger.warning(f"Auto-migration on startup error: {e}")
    # Cleanup orphan RUNNING entries from previous crash/restart
    try:
        conn = psycopg2.connect(pg_url)
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE odoo.sync_run_log
                SET status = 'ERROR',
                    error_message = 'Interrumpido por reinicio del servidor',
                    ended_at = now()
                WHERE status = 'RUNNING'
            """)
            cleaned = cur.rowcount
            conn.commit()
        conn.close()
        if cleaned:
            logger.info(f"Cleaned {cleaned} orphan RUNNING sync entries")
    except Exception as e:
        logger.warning(f"Cleanup orphan RUNNING failed: {e}")
    # Start scheduler
    scheduler.start()


@api_router.get("/")
async def root():
    return {"message": "Odoo ODS Schema Manager API"}


@api_router.get("/connection/test")
async def test_connection():
    """Test PostgreSQL connection and return server info."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                cur.execute("SELECT current_database(), current_schema()")
                db_info = cur.fetchone()
        return {
            "connected": True,
            "version": version,
            "database": db_info[0],
            "schema": db_info[1],
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@api_router.post("/migrate")
async def execute_migration():
    """Execute the full migration (idempotent)."""
    started = datetime.now(timezone.utc)
    result = run_migration()
    ended = datetime.now(timezone.utc)
    return {
        **result,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_ms": int((ended - started).total_seconds() * 1000),
    }


@api_router.get("/schema/tables")
async def get_schema_tables():
    """Get all odoo.* tables with row counts and column counts."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                tables = []
                for table_name in ODOO_TABLES:
                    try:
                        cur.execute(f"""
                            SELECT count(*) as row_count 
                            FROM odoo.{table_name}
                        """)
                        row_count = cur.fetchone()["row_count"]

                        cur.execute(f"""
                            SELECT count(*) as col_count 
                            FROM information_schema.columns 
                            WHERE table_schema = 'odoo' AND table_name = '{table_name}'
                        """)
                        col_count = cur.fetchone()["col_count"]

                        tables.append({
                            "name": table_name,
                            "type": "TABLE",
                            "row_count": row_count,
                            "col_count": col_count,
                            "exists": True,
                        })
                    except Exception:
                        conn.rollback()
                        tables.append({
                            "name": table_name,
                            "type": "TABLE",
                            "row_count": 0,
                            "col_count": 0,
                            "exists": False,
                        })

                for view_name in ODOO_VIEWS:
                    try:
                        cur.execute(f"""
                            SELECT count(*) as col_count 
                            FROM information_schema.columns 
                            WHERE table_schema = 'odoo' AND table_name = '{view_name}'
                        """)
                        col_count = cur.fetchone()["col_count"]
                        tables.append({
                            "name": view_name,
                            "type": "VIEW",
                            "row_count": None,
                            "col_count": col_count,
                            "exists": True,
                        })
                    except Exception:
                        conn.rollback()
                        tables.append({
                            "name": view_name,
                            "type": "VIEW",
                            "row_count": None,
                            "col_count": 0,
                            "exists": False,
                        })

        return {"tables": tables}
    except Exception as e:
        return {"tables": [], "error": str(e)}


@api_router.get("/schema/indexes")
async def get_schema_indexes():
    """Get all indexes in the odoo schema."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        indexname,
                        tablename,
                        indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'odoo'
                    ORDER BY tablename, indexname
                """)
                indexes = cur.fetchall()
        return {"indexes": indexes}
    except Exception as e:
        return {"indexes": [], "error": str(e)}


@api_router.get("/sync-jobs")
async def get_sync_jobs():
    """Get all sync jobs."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        job_code, enabled, schedule_type, 
                        run_time::text as run_time, priority, mode,
                        chunk_size, company_scope, filters_json,
                        last_run_at, last_success_at, last_cursor,
                        last_error
                    FROM odoo.sync_job
                    ORDER BY priority
                """)
                jobs = cur.fetchall()
                for job in jobs:
                    for key in ['last_run_at', 'last_success_at', 'last_cursor']:
                        if job[key] is not None:
                            job[key] = job[key].isoformat()
        return {"jobs": jobs}
    except Exception as e:
        return {"jobs": [], "error": str(e)}


@api_router.get("/sync-logs")
async def get_sync_logs():
    """Get recent sync run logs."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id, job_code, company_key,
                        started_at, ended_at, status,
                        rows_upserted, rows_updated, error_message
                    FROM odoo.sync_run_log
                    ORDER BY started_at DESC
                    LIMIT 100
                """)
                logs = cur.fetchall()
                for log in logs:
                    for key in ['started_at', 'ended_at']:
                        if log[key] is not None:
                            log[key] = log[key].isoformat()
        return {"logs": logs}
    except Exception as e:
        return {"logs": [], "error": str(e)}


@api_router.get("/migration/status")
async def get_migration_status():
    """Check if the schema exists and all tables are present."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.schemata 
                        WHERE schema_name = 'odoo'
                    ) as schema_exists
                """)
                schema_exists = cur.fetchone()["schema_exists"]

                if not schema_exists:
                    return {
                        "schema_exists": False,
                        "tables_expected": len(ODOO_TABLES),
                        "tables_found": 0,
                        "views_expected": len(ODOO_VIEWS),
                        "views_found": 0,
                        "all_ok": False,
                    }

                cur.execute("""
                    SELECT count(*) as cnt 
                    FROM information_schema.tables 
                    WHERE table_schema = 'odoo' 
                      AND table_type = 'BASE TABLE'
                """)
                tables_found = cur.fetchone()["cnt"]

                cur.execute("""
                    SELECT count(*) as cnt 
                    FROM information_schema.views 
                    WHERE table_schema = 'odoo'
                """)
                views_found = cur.fetchone()["cnt"]

                cur.execute("""
                    SELECT count(*) as cnt 
                    FROM pg_indexes 
                    WHERE schemaname = 'odoo'
                """)
                indexes_count = cur.fetchone()["cnt"]

        all_ok = (tables_found >= len(ODOO_TABLES) and views_found >= len(ODOO_VIEWS))
        return {
            "schema_exists": schema_exists,
            "tables_expected": len(ODOO_TABLES),
            "tables_found": tables_found,
            "views_expected": len(ODOO_VIEWS),
            "views_found": views_found,
            "indexes_count": indexes_count,
            "all_ok": all_ok,
        }
    except Exception as e:
        return {
            "schema_exists": False,
            "tables_expected": len(ODOO_TABLES),
            "tables_found": 0,
            "views_expected": len(ODOO_VIEWS),
            "views_found": 0,
            "all_ok": False,
            "error": str(e),
        }


# ----------------------------------------------------------------
# SYNC ENDPOINTS
# ----------------------------------------------------------------

class SyncRunRequest(BaseModel):
    job_code: Optional[str] = None
    mode: Optional[str] = None  # INCREMENTAL or FULL
    target: Optional[str] = 'ALL'  # ALL, GLOBAL_ONLY, POS_ONLY
    company_key: Optional[str] = None  # Ambission or ProyectoModa


@api_router.post("/sync/run")
async def run_sync(request: SyncRunRequest):
    """Trigger a sync run. Runs in background thread."""
    from sync_engine import SyncService
    started = datetime.now(timezone.utc)
    try:
        svc = SyncService()
        result = await asyncio.to_thread(
            svc.run_sync,
            job_code=request.job_code,
            mode=request.mode,
            target=request.target or 'ALL',
            company_key=request.company_key,
        )
        ended = datetime.now(timezone.utc)
        return {
            **result,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_ms": int((ended - started).total_seconds() * 1000),
        }
    except Exception as e:
        ended = datetime.now(timezone.utc)
        return {
            "success": False,
            "message": str(e),
            "results": [],
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_ms": int((ended - started).total_seconds() * 1000),
        }


@api_router.get("/sync/status")
async def get_sync_status():
    """Get sync jobs and recent logs."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        job_code, enabled, schedule_type, 
                        run_time::text as run_time, priority, mode,
                        chunk_size, company_scope,
                        last_run_at, last_success_at, last_cursor,
                        last_error
                    FROM odoo.sync_job
                    ORDER BY priority
                """)
                jobs = cur.fetchall()
                for job in jobs:
                    for key in ['last_run_at', 'last_success_at', 'last_cursor']:
                        if job[key] is not None:
                            job[key] = job[key].isoformat()

                cur.execute("""
                    SELECT 
                        id, job_code, company_key,
                        started_at, ended_at, status,
                        rows_upserted, rows_updated, error_message
                    FROM odoo.sync_run_log
                    ORDER BY started_at DESC
                    LIMIT 50
                """)
                logs = cur.fetchall()
                for log in logs:
                    for key in ['started_at', 'ended_at']:
                        if log[key] is not None:
                            log[key] = log[key].isoformat()

        return {"jobs": jobs, "logs": logs}
    except Exception as e:
        return {"jobs": [], "logs": [], "error": str(e)}


@api_router.post("/sync/job/{job_code}/update")
async def update_sync_job(job_code: str, enabled: Optional[bool] = None, mode: Optional[str] = None, chunk_size: Optional[int] = None):
    """Update a sync job configuration."""
    try:
        updates = []
        values = []
        if enabled is not None:
            updates.append("enabled = %s")
            values.append(enabled)
        if mode is not None:
            updates.append("mode = %s")
            values.append(mode)
        if chunk_size is not None:
            updates.append("chunk_size = %s")
            values.append(chunk_size)
        if not updates:
            return {"success": False, "message": "No fields to update"}
        values.append(job_code)
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE odoo.sync_job SET {', '.join(updates)} WHERE job_code = %s", values)
            conn.commit()
        return {"success": True, "message": f"Job {job_code} actualizado"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@api_router.get("/stock-locations")
async def get_stock_locations(search: Optional[str] = None):
    """Get all stock locations (GLOBAL) with optional search."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if search and search.strip():
                    s = f"%{search.strip()}%"
                    cur.execute("""
                        SELECT odoo_id, x_nombre, name, complete_name, usage, active,
                               location_id, company_id, odoo_write_date
                        FROM odoo.stock_location
                        WHERE company_key = 'GLOBAL'
                          AND (x_nombre ILIKE %s OR name ILIKE %s OR complete_name ILIKE %s)
                        ORDER BY odoo_write_date DESC NULLS LAST
                    """, (s, s, s))
                else:
                    cur.execute("""
                        SELECT odoo_id, x_nombre, name, complete_name, usage, active,
                               location_id, company_id, odoo_write_date
                        FROM odoo.stock_location
                        WHERE company_key = 'GLOBAL'
                        ORDER BY odoo_write_date DESC NULLS LAST
                    """)
                locations = cur.fetchall()
                for loc in locations:
                    if loc['odoo_write_date'] is not None:
                        loc['odoo_write_date'] = loc['odoo_write_date'].isoformat()
        return {"locations": locations}
    except Exception as e:
        return {"locations": [], "error": str(e)}


@api_router.get("/stock-quants")
async def get_stock_quants(
    product_id: Optional[int] = None,
    location_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Get stock quants (GLOBAL) with pagination."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = ["company_key = 'GLOBAL'"]
                params = []
                if product_id:
                    conditions.append("product_id = %s")
                    params.append(product_id)
                if location_id:
                    conditions.append("location_id = %s")
                    params.append(location_id)
                where = " AND ".join(conditions)
                offset = (page - 1) * page_size
                cur.execute(f"SELECT count(*) as total FROM odoo.stock_quant WHERE {where}", params)
                total = cur.fetchone()["total"]
                cur.execute(f"""
                    SELECT odoo_id, product_id, location_id, qty, reserved_qty, in_date, odoo_write_date
                    FROM odoo.stock_quant WHERE {where}
                    ORDER BY odoo_write_date DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """, params + [page_size, offset])
                rows = cur.fetchall()
                for r in rows:
                    for k in ('qty', 'reserved_qty'):
                        if r[k] is not None: r[k] = float(r[k])
                    for k in ('in_date', 'odoo_write_date'):
                        if r[k] is not None: r[k] = r[k].isoformat()
        return {"rows": rows, "total": total, "page": page, "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0}
    except Exception as e:
        return {"rows": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "error": str(e)}


@api_router.get("/stock-by-product")
async def get_stock_by_product(
    only_available: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Get stock aggregated by product from internal locations."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                where = "WHERE available_qty > 0" if only_available else ""
                cur.execute(f"SELECT count(*) as total FROM odoo.v_stock_by_product {where}")
                total = cur.fetchone()["total"]
                offset = (page - 1) * page_size
                cur.execute(f"""
                    SELECT product_id, qty, reserved_qty, available_qty
                    FROM odoo.v_stock_by_product {where}
                    ORDER BY available_qty DESC
                    LIMIT %s OFFSET %s
                """, (page_size, offset))
                rows = cur.fetchall()
                for r in rows:
                    for k in ('qty', 'reserved_qty', 'available_qty'):
                        if r[k] is not None: r[k] = float(r[k])
        return {"rows": rows, "total": total, "page": page, "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0}
    except Exception as e:
        return {"rows": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "error": str(e)}


@api_router.get("/stock-by-location")
async def get_stock_by_location(
    location_id: Optional[int] = None,
    only_available: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Get stock by product+location from internal locations, with location name."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = []
                params = []
                if location_id:
                    conditions.append("v.location_id = %s")
                    params.append(location_id)
                if only_available:
                    conditions.append("v.available_qty > 0")
                where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                cur.execute(f"""
                    SELECT count(*) as total FROM odoo.v_stock_by_product_location v {where}
                """, params)
                total = cur.fetchone()["total"]
                offset = (page - 1) * page_size
                cur.execute(f"""
                    SELECT v.product_id, v.location_id, v.available_qty, v.qty, v.reserved_qty,
                           sl.x_nombre as location_name, sl.name as location_raw_name
                    FROM odoo.v_stock_by_product_location v
                    LEFT JOIN odoo.stock_location sl ON sl.company_key='GLOBAL' AND sl.odoo_id=v.location_id
                    {where}
                    ORDER BY v.available_qty DESC
                    LIMIT %s OFFSET %s
                """, params + [page_size, offset])
                rows = cur.fetchall()
                for r in rows:
                    for k in ('qty', 'reserved_qty', 'available_qty'):
                        if r[k] is not None: r[k] = float(r[k])
        return {"rows": rows, "total": total, "page": page, "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0}
    except Exception as e:
        return {"rows": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "error": str(e)}


@api_router.get("/pos-lines-full")
async def get_pos_lines_full(
    company_key: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_cancelled: Optional[bool] = None,
    marca: Optional[str] = None,
    tipo: Optional[str] = None,
    tela: Optional[str] = None,
    talla: Optional[str] = None,
    color: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Query v_pos_line_full with filters and pagination."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = ["company_key IN ('Ambission','ProyectoModa')"]
                params = []

                if company_key:
                    conditions.append("company_key = %s")
                    params.append(company_key)
                if date_from:
                    conditions.append("date_order >= %s")
                    params.append(date_from)
                if date_to:
                    conditions.append("date_order <= %s")
                    params.append(date_to)
                if is_cancelled is not None:
                    conditions.append("is_cancelled = %s")
                    params.append(is_cancelled)
                if marca:
                    conditions.append("marca ILIKE %s")
                    params.append(f"%{marca}%")
                if tipo:
                    conditions.append("tipo ILIKE %s")
                    params.append(f"%{tipo}%")
                if tela:
                    conditions.append("tela ILIKE %s")
                    params.append(f"%{tela}%")
                if talla:
                    conditions.append("talla ILIKE %s")
                    params.append(f"%{talla}%")
                if color:
                    conditions.append("color ILIKE %s")
                    params.append(f"%{color}%")

                where = " AND ".join(conditions)
                offset = (page - 1) * page_size

                # Count
                cur.execute(f"SELECT count(*) as total FROM odoo.v_pos_line_full WHERE {where}", params)
                total = cur.fetchone()["total"]

                # Data
                cur.execute(f"""
                    SELECT company_key, date_order, cuenta_partner_id, contacto_partner_id, user_id,
                           state, is_cancelled, reserva, reserva_use_id,
                           order_id, pos_order_line_id, product_id, qty, price_unit, discount, price_subtotal,
                           product_tmpl_id, barcode, talla, color, marca, tipo, tela, entalle, list_price
                    FROM odoo.v_pos_line_full
                    WHERE {where}
                    ORDER BY date_order DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """, params + [page_size, offset])
                rows = cur.fetchall()
                for r in rows:
                    if r['date_order'] is not None:
                        r['date_order'] = r['date_order'].isoformat()
                    for k in ('qty', 'price_unit', 'discount', 'price_subtotal', 'list_price'):
                        if r[k] is not None:
                            r[k] = float(r[k])

        return {
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }
    except Exception as e:
        return {"rows": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "error": str(e)}


@api_router.get("/health")
async def get_health():
    """Health check: table counts, last dates, integrity, errors."""
    try:
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Table counts + max write_date
                tables_health = []
                for tbl, ck_filter in [
                    ("res_partner", "company_key='GLOBAL'"),
                    ("product_template", "company_key='GLOBAL'"),
                    ("product_product", "company_key='GLOBAL'"),
                    ("stock_location", "company_key='GLOBAL'"),
                    ("stock_quant", "company_key='GLOBAL'"),
                    ("pos_order", "1=1"),
                    ("pos_order_line", "1=1"),
                ]:
                    cur.execute(f"SELECT count(*) as cnt, max(odoo_write_date) as max_wd FROM odoo.{tbl} WHERE {ck_filter}")
                    r = cur.fetchone()
                    tables_health.append({
                        "table": tbl,
                        "count": r["cnt"],
                        "max_write_date": r["max_wd"].isoformat() if r["max_wd"] else None,
                    })

                # POS by company
                cur.execute("""
                    SELECT company_key, count(*) as cnt, max(odoo_write_date) as max_wd
                    FROM odoo.pos_order GROUP BY company_key ORDER BY 1
                """)
                pos_by_company = []
                for r in cur.fetchall():
                    pos_by_company.append({
                        "company_key": r["company_key"],
                        "count": r["cnt"],
                        "max_write_date": r["max_wd"].isoformat() if r["max_wd"] else None,
                    })

                # Integrity: lines without header
                cur.execute("""
                    SELECT count(*) as orphan_lines
                    FROM odoo.pos_order_line l
                    LEFT JOIN odoo.pos_order o
                        ON o.company_key = l.company_key AND o.odoo_id = l.order_id
                    WHERE o.odoo_id IS NULL
                """)
                orphan_lines = cur.fetchone()["orphan_lines"]

                # Last errors
                cur.execute("""
                    SELECT id, job_code, company_key, started_at, ended_at, error_message
                    FROM odoo.sync_run_log WHERE status='ERROR'
                    ORDER BY started_at DESC LIMIT 10
                """)
                errors = cur.fetchall()
                for e in errors:
                    for k in ('started_at', 'ended_at'):
                        if e[k] is not None:
                            e[k] = e[k].isoformat()

        return {
            "tables": tables_health,
            "pos_by_company": pos_by_company,
            "orphan_lines": orphan_lines,
            "recent_errors": errors,
        }
    except Exception as e:
        return {"tables": [], "pos_by_company": [], "orphan_lines": -1, "recent_errors": [], "error": str(e)}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    scheduler.stop()
    client.close()
