# Odoo ODS - Operational Data Store

## Problema Original
Crear un Operational Data Store (ODS) en PostgreSQL para replicar datos de Odoo 10 vía XML-RPC. El objetivo es crear un espejo de datos de Odoo en un esquema `odoo` para alimentar futuros sistemas de CRM, Finanzas y Producción.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2-binary) + XML-RPC
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Datos:** Modelo multi-empresa (`company_key`): maestros=GLOBAL, POS=por empresa

## Fases Completadas

### Fase 1 - Schema & Vistas ✅
Schema `odoo` con tablas: res_company, res_users, res_partner, product_template, product_product, atributos, pos_order, pos_order_line. Vistas: v_product_variant_flat, v_partner_account_map, v_pos_order_enriched, v_pos_line_full.

### Fase 2 - Sync Engine ✅  
Motor de sincronización incremental vía XML-RPC (write_date cursor). Batch upserts con execute_values. Paginación por ID. Advisory lock. Scheduler. +1.25M registros sincronizados.

### Fase 3 - Stock Locations ✅
Tabla odoo.stock_location + sync. 52 ubicaciones sincronizadas.

### Fase 4 - UI de Validación ✅
Dashboard, Historial, Panel de control, Locations, POS Lines Full, Health.

### Fase 5 - Stock Actual (stock.quant) ✅ [13-Feb-2026]
- **Tabla** `odoo.stock_quant`: PK(company_key, odoo_id), campos qty, reserved_qty, in_date, audit fields
- **Sync** `STOCK_QUANTS`: chunk_size=5000, company_scope=GLOBAL. Detección automática de campo qty/quantity y reserved_quantity. Inserción progresiva por lotes. **1,042,549 registros sincronizados.**
- **Vistas SQL**:
  - `v_stock_by_product_location`: stock por producto+ubicación (solo internal/active). 16,811 filas.
  - `v_stock_by_product`: stock agregado por producto. 8,046 productos con stock.
- **UI**: 3 páginas nuevas:
  - `/stock-quants`: tabla paginada con filtros product_id/location_id
  - `/stock-by-product`: stock disponible por producto con toggle "Solo disponible"
  - `/stock-by-location`: stock por tienda con nombre de tienda vía lookup

## Endpoints API
- `POST /api/sync/run` - Ejecutar sync manual
- `GET /api/sync/status` - Estado de jobs y logs
- `GET /api/health` - Salud del sistema (incluye stock_quant)
- `GET /api/stock-quants` - Quants paginados con filtros
- `GET /api/stock-by-product` - Stock agregado por producto
- `GET /api/stock-by-location` - Stock por producto+tienda
- `GET /api/pos-lines-full` - Líneas POS enriquecidas
- `GET /api/locations` - Ubicaciones
- `GET /api/sync-logs` - Historial de sync

## Backlog
No hay tareas pendientes adicionales.
