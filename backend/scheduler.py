"""
Scheduler: runs every 60 seconds, checks sync_job schedules, triggers syncs.
"""
import asyncio
import logging
import psycopg2
from datetime import datetime, timezone, timedelta
import os

logger = logging.getLogger(__name__)

MASTER_JOBS = ['RES_COMPANY', 'RES_USERS', 'RES_PARTNER', 'PRODUCTS', 'ATTRIBUTES', 'STOCK_LOCATIONS', 'STOCK_QUANTS']
POS_JOBS = ['POS_ORDERS']
MULTI_JOBS = ['AR_CREDIT_INVOICES']


class SyncScheduler:
    def __init__(self):
        self.pg_url = os.environ['PG_URL']
        self._running = False
        self._task = None

    def start(self):
        """Start the scheduler as a background asyncio task."""
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Scheduler stopped")

    async def _loop(self):
        """Main loop: check every 60 seconds."""
        while True:
            try:
                await self._check_and_run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)
            await asyncio.sleep(60)

    async def _check_and_run(self):
        """Check if any job should run now."""
        now = datetime.now(timezone.utc)
        current_time = now.strftime('%H:%M')

        conn = psycopg2.connect(self.pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT job_code, schedule_type, run_time, last_run_at
                    FROM odoo.sync_job
                    WHERE enabled = true
                """)
                jobs = cur.fetchall()
        finally:
            conn.close()

        jobs_to_run = []
        for job_code, schedule_type, run_time, last_run_at in jobs:
            if schedule_type == 'HOURLY':
                # Run if never ran or last run > 1 hour ago
                if last_run_at and (now - last_run_at) < timedelta(hours=1):
                    continue
                jobs_to_run.append(job_code)
            elif schedule_type == 'DAILY':
                job_time_str = run_time.strftime('%H:%M') if run_time else None
                if job_time_str != current_time:
                    continue
                if last_run_at and (now - last_run_at) < timedelta(hours=1):
                    continue
                jobs_to_run.append(job_code)

        if jobs_to_run:
            logger.info(f"Scheduler triggering jobs: {jobs_to_run}")
            # Import here to avoid circular imports
            from sync_engine import SyncService
            svc = SyncService()
            for jc in jobs_to_run:
                try:
                    if jc in MASTER_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc, target='GLOBAL_ONLY')
                    elif jc in POS_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc, target='POS_ONLY')
                    elif jc in MULTI_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc)
                except Exception as e:
                    logger.error(f"Scheduler job {jc} failed: {e}")
