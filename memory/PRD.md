# Odoo ODS - Product Requirements Document

## Problema Original
Crear un Operational Data Store (ODS) en PostgreSQL para replicar datos de una instancia de Odoo 10. El objetivo es crear un espejo de los datos de Odoo en un esquema "odoo" para alimentar futuros sistemas de CRM, Finanzas y Producción.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Sync:** Motor de sincronización incremental/completa con scheduler (DAILY/HOURLY)
- **Multi-empresa:** Ambission y ProyectoModa

## Fases Completadas

### Fase 1-5: Todas completadas
- Schema odoo, sync engine, stock locations, UI, stock actual

### Fix: Campo tipo con x_tipo_resumen (COMPLETADO - 13 Feb 2026)
- **Root cause:** `x_tipo` en Odoo 10 retorna como string (name), no como [id, name]. `xid()` fallaba silenciosamente.
- **Fix:** Nuevo mapeo nombre->x_tipo_resumen via `search_read` de product.tipo. Ej: "Bermuda Cargo" -> "Short Denim"
- Vistas SQL de stock actualizadas con product_name, marca, tipo via JOINs
- Endpoints y frontend de stock actualizados
- Sync FULL de productos ejecutado exitosamente (100,143 filas)
- Verificado: 0 productos con "Bermuda Cargo", 75 con "Short Denim"

## Tablas Principales
- odoo.sync_job, sync_run_log, res_company, res_users, res_partner
- odoo.product_template, product_product, product_attribute*
- odoo.pos_order, pos_order_line, stock_location, stock_quant

## Endpoints API
- POST /api/sync/run, GET /api/sync/status, GET /api/health
- GET /api/pos-lines-full, GET /api/stock-quants
- GET /api/stock-by-product, GET /api/stock-by-location
- GET /api/stock-locations, POST /api/migrate

## Estado: Proyecto funcionalmente completo
