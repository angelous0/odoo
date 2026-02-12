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
                # Check schema exists
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

                # Count existing tables
                cur.execute("""
                    SELECT count(*) as cnt 
                    FROM information_schema.tables 
                    WHERE table_schema = 'odoo' 
                      AND table_type = 'BASE TABLE'
                """)
                tables_found = cur.fetchone()["cnt"]

                # Count existing views
                cur.execute("""
                    SELECT count(*) as cnt 
                    FROM information_schema.views 
                    WHERE table_schema = 'odoo'
                """)
                views_found = cur.fetchone()["cnt"]

                # Count total indexes
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
    client.close()
