# PRD - Odoo ODS Schema Manager

## Problema Original
Sistema de sincronización de datos desde Odoo 10 a un ODS en PostgreSQL, con backend FastAPI y frontend React. Sincroniza maestros (productos, partners), transacciones (POS, facturas de crédito) y datos de inventario (stock, ubicaciones).

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Base de datos:** PostgreSQL con schema `odoo`, migración idempotente, vistas SQL
- **Sincronización:** Incremental resiliente con reintentos para errores 502

## Funcionalidades Implementadas

### Core
- Sincronización incremental multi-empresa (Ambission, ProyectoModa, GLOBAL)
- Dashboard con monitoreo de sincronización
- Historial de sync runs con logs
- Health check con integridad de datos

### Módulos de Datos
- **Productos:** Sincronización con mapeo de tipo/entalle/tela
- **Partners:** Sincronización con campos CRM
- **POS:** Órdenes y líneas con vista enriquecida (v_pos_line_full)
- **Stock:** Quants, ubicaciones, vistas por producto y por tienda
- **Facturas de Crédito:** Sincronización completa con líneas

### Filtros de Catálogo (Feb 2026)
- **Exclusión "paneton":** Filtro `NOT ILIKE '%paneton%'` en vistas SQL `v_stock_by_product_location` y `v_stock_by_product`
- **Toggle archivados:** Parámetro `include_archived` en endpoints `/api/stock-by-product` y `/api/stock-by-location`. Frontend con botón toggle y badges "Archivado"/"Activo"

## Endpoints API
- `POST /api/migrate` - Migración idempotente
- `POST /api/sync/run` - Ejecutar sincronización
- `GET /api/sync/status` - Estado de jobs
- `GET /api/stock-by-product` - Stock por producto (include_archived, only_available)
- `GET /api/stock-by-location` - Stock por tienda (include_archived, only_available, location_id)
- `GET /api/pos-lines-full` - Líneas POS enriquecidas
- `GET /api/credit-invoices` - Facturas de crédito
- `GET /api/health` - Health check

## Schema DB (key tables)
- `odoo.product_template` - Productos con tipo, entalle, tela, active
- `odoo.stock_quant` - Quants de stock
- `odoo.v_stock_by_product` - Vista agregada (excluye paneton, incluye active)
- `odoo.v_stock_by_product_location` - Vista por ubicación (excluye paneton, incluye active)

## Backlog
- No hay tareas pendientes definidas por el usuario.
