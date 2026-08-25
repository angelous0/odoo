"""
Scheduler: runs every 60 seconds, checks sync_job schedules, triggers syncs.
"""
import asyncio
import logging
import psycopg2
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os

# Única fuente de verdad para las listas de jobs (antes estaban duplicadas
# aquí y se desincronizaban — STOCK_MOVE llegó a faltar en esta copia).
from sync_engine import MASTER_JOBS, POS_JOBS, MULTI_JOBS

logger = logging.getLogger(__name__)

# Timezone para interpretar sync_job.run_time de los jobs DAILY.
# Default UTC (comportamiento histórico). Para hora de Perú:
# SCHEDULER_TZ=America/Lima en backend/.env
SCHED_TZ = ZoneInfo(os.environ.get('SCHEDULER_TZ', 'UTC'))

# Lectura COMPLETA periódica. El sync normal es incremental y no puede detectar
# registros BORRADOS en Odoo: se quedan congelados en la copia local con su
# último estado. Para stock.move eso significa movimientos "pendientes" que ya
# no existen, y que el modo Proyectado sigue descontando (caso MORTAIN 08/2026).
# Solo el modo FULL corre la limpieza de huérfanos, así que hay que forzarlo
# cada tanto.
FULL_JOBS = [j.strip() for j in os.environ.get('SYNC_FULL_JOBS', 'STOCK_MOVE').split(',') if j.strip()]
FULL_WEEKDAY = int(os.environ.get('SYNC_FULL_WEEKDAY', 6))   # 0=lunes … 6=domingo
# La hora se interpreta en SCHEDULER_TZ, que por defecto es UTC. 8 UTC son las
# 3 a.m. en Perú — madrugada de verdad. Si se cambia SCHEDULER_TZ a
# America/Lima, acá hay que poner 3.
FULL_HOUR = int(os.environ.get('SYNC_FULL_HOUR', 8))


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
        local_now = now.astimezone(SCHED_TZ)

        conn = psycopg2.connect(self.pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT job_code, schedule_type, run_time, last_run_at
                    FROM odoo.sync_job
                    WHERE enabled = true
                """)
                jobs = cur.fetchall()
                # Jobs con una corrida EN CURSO (disparada a mano desde la app
                # o por un ciclo anterior que todavía no terminó). `last_run_at`
                # recién se escribe al final, así que sin este chequeo el loop
                # los volvía a lanzar cada 60s y quedaban varias corridas del
                # mismo job pegándole a Odoo a la vez. Con la limpieza de
                # huérfanos eso es peligroso: dos FULL solapados pueden borrar
                # filas que el otro todavía no refrescó.
                cur.execute("""
                    SELECT DISTINCT job_code FROM odoo.sync_run_log
                    WHERE status = 'RUNNING' AND started_at > now() - interval '3 hours'
                """)
                en_curso = {r[0] for r in cur.fetchall()}
        finally:
            conn.close()

        jobs_to_run = []
        for job_code, schedule_type, run_time, last_run_at in jobs:
            if job_code in en_curso:
                logger.debug(f"Scheduler skip {job_code}: ya hay una corrida en curso")
                continue
            if schedule_type == 'HOURLY':
                # Run if never ran or last run > 1 hour ago
                if last_run_at and (now - last_run_at) < timedelta(hours=1):
                    continue
                jobs_to_run.append(job_code)
            elif schedule_type == 'DAILY':
                # Antes: comparación exacta de 'HH:MM' — si el loop estaba
                # ocupado en ese minuto (un sync largo), el job se saltaba
                # el día entero. Ahora: correr si ya pasó la hora programada
                # de hoy Y la última corrida fue antes de esa hora.
                if run_time is None:
                    continue
                run_dt_today = local_now.replace(
                    hour=run_time.hour, minute=run_time.minute,
                    second=0, microsecond=0,
                )
                if local_now < run_dt_today:
                    continue  # todavía no llega la hora de hoy
                if last_run_at and last_run_at >= run_dt_today.astimezone(timezone.utc):
                    continue  # ya corrió hoy
                jobs_to_run.append(job_code)

        # ¿Toca lectura completa? Solo en el día y hora configurados. El guard
        # HOURLY/DAILY de arriba ya impide que se repita dentro de esa hora.
        es_ventana_full = (local_now.weekday() == FULL_WEEKDAY and local_now.hour == FULL_HOUR)

        if jobs_to_run:
            logger.info(f"Scheduler triggering jobs: {jobs_to_run}"
                        + (f" (FULL para {[j for j in jobs_to_run if j in FULL_JOBS]})" if es_ventana_full else ""))
            # Import here to avoid circular imports
            from sync_engine import SyncService
            svc = SyncService()
            for jc in jobs_to_run:
                modo = 'full' if (es_ventana_full and jc in FULL_JOBS) else None
                if modo:
                    logger.info(f"  {jc}: lectura COMPLETA (limpia huérfanos)")
                try:
                    if jc in MASTER_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc, target='GLOBAL_ONLY', mode=modo)
                    elif jc in POS_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc, target='POS_ONLY', mode=modo)
                    elif jc in MULTI_JOBS:
                        await asyncio.to_thread(svc.run_sync, job_code=jc, mode=modo)
                except Exception as e:
                    logger.error(f"Scheduler job {jc} failed: {e}")
