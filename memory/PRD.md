# Odoo ODS - Product Requirements Document

## Problema Original
Crear un Operational Data Store (ODS) en PostgreSQL para replicar datos de una instancia de Odoo 10. El objetivo es crear un espejo de los datos de Odoo en un esquema "odoo" para alimentar futuros sistemas de CRM, Finanzas y Producción.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Sync:** Motor de sincronización incremental/completa con scheduler (DAILY/HOURLY)
- **Multi-empresa:** Ambission y ProyectoModa

## Fases Completadas

### Fase 1: Schema & Vistas (COMPLETADO)
- Schema `odoo` con tablas para maestros, productos, atributos, POS
- Vistas SQL: v_product_variant_flat, v_partner_account_map, v_pos_order_enriched, v_pos_line_full

### Fase 2: Sync Engine (COMPLETADO)
- Motor incremental via XML-RPC con batch upserts
- Advisory locks para prevenir concurrencia
- Soporte multi-empresa

### Fase 3: Stock Locations (COMPLETADO)
- Tabla odoo.stock_location sincronizada

### Fase 4: UI y Vistas de Validación (COMPLETADO)
- Dashboard, Historial, Locations, POS Lines, Health
- Feedback visual: toasts, barras de progreso, auto-refresco

### Fase 5: Stock Actual (COMPLETADO)
- stock.quant sincronizado (1M+ registros)
- Vistas v_stock_by_product y v_stock_by_product_location
- Páginas: Stock Quants, Stock x Producto, Stock x Tienda

### Fix: Campo tipo con x_tipo_resumen (COMPLETADO - 13 Feb 2026)
- Sync de product_template usa x_tipo_resumen del modelo product.tipo
- Vistas de stock actualizadas para incluir product_name, marca, tipo via JOINs
- Endpoints stock-by-product y stock-by-location retornan info de producto
- Frontend actualizado en todas las páginas de stock
- Testing: 100% backend y frontend

## Tablas Principales
- odoo.sync_job, odoo.sync_run_log
- odoo.res_company, odoo.res_users, odoo.res_partner
- odoo.product_template, odoo.product_product
- odoo.product_attribute, odoo.product_attribute_value
- odoo.pos_order, odoo.pos_order_line
- odoo.stock_location, odoo.stock_quant

## Endpoints API
- POST /api/sync/run, GET /api/sync/status
- GET /api/health, GET /api/pos-lines-full
- GET /api/stock-quants, GET /api/stock-by-product, GET /api/stock-by-location
- GET /api/stock-locations, POST /api/migrate

## Estado: Proyecto funcionalmente completo
