# PRD - Odoo ODS Schema Manager

## Problema Original
Sistema de sincronizacion de datos desde Odoo 10 a un ODS en PostgreSQL, con backend FastAPI y frontend React. Sincroniza maestros (productos, partners), transacciones (POS, facturas de credito) y datos de inventario (stock, ubicaciones).

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Base de datos:** PostgreSQL con schema `odoo`, migracion idempotente, vistas SQL
- **Sincronizacion:** Incremental resiliente con reintentos para errores 502

## Funcionalidades Implementadas

### Core
- Sincronizacion incremental multi-empresa (Ambission, ProyectoModa, GLOBAL)
- Dashboard con monitoreo de sincronizacion
- Historial de sync runs con logs
- Health check con integridad de datos

### Modulos de Datos
- **Productos:** Sincronizacion con mapeo de tipo/entalle/tela, linea_negocio (id + nombre)
- **Partners:** Sincronizacion con campos CRM (state_name, phone, mobile)
- **POS:** Ordenes y lineas con vista enriquecida (v_pos_line_full) incluyendo linea_negocio_id y linea_negocio_nombre, location_id
- **Stock:** Quants, ubicaciones, vistas por producto y por tienda
- **Facturas de Credito:** Sincronizacion completa con lineas
- **x_linea_negocio:** Tabla maestra sincronizada desde Odoo

### Filtros de Catalogo (Feb 2026)
- Exclusion "paneton" y "publicitario" en vistas SQL
- Toggle archivados en endpoints stock
- Sync incluye archivados con active_test: False

### Sync Control (Mar 2026)
- Pagina Sync Control con monitor de 10 jobs, badges de estado, botones Run
- Botones macro: Clientes, Ventas, Productos (X_LINEA_NEGOCIO+PRODUCTS+ATTRIBUTES), Stock, Creditos
- Endpoints: GET /api/odoo-sync/job-status, POST /api/odoo-sync/run, POST /api/odoo-sync/run-batch

### Cambios Mar 11 2026
- Nueva tabla x_linea_negocio con job de sync
- Campos linea_negocio_id (INT) + linea_negocio (TEXT) en product_template
- Fix purchase_ok: eliminado filtro que excluia productos validos
- Vista v_pos_line_full enriquecida con linea_negocio_id y linea_negocio_nombre
- Endpoint /api/pos-lines-full expone linea_negocio_id y linea_negocio_nombre

## Endpoints API
- POST /api/migrate - Migracion idempotente
- POST /api/sync/run - Ejecutar sincronizacion
- GET /api/sync/status - Estado de jobs
- GET /api/stock-by-product - Stock por producto
- GET /api/stock-by-location - Stock por tienda
- GET /api/pos-lines-full - Lineas POS enriquecidas (incluye linea_negocio_id, linea_negocio_nombre)
- GET /api/credit-invoices - Facturas de credito
- GET /api/health - Health check
- POST /api/sync/pos - Sync POS con metricas (protegido por token)
- GET /api/odoo-sync/job-status - Estado de todos los jobs
- POST /api/odoo-sync/run - Ejecutar job individual
- POST /api/odoo-sync/run-batch - Ejecutar batch de jobs

## Schema DB
- odoo.product_template: incluye linea_negocio_id (INT), linea_negocio (TEXT)
- odoo.x_linea_negocio: tabla maestra de lineas de negocio
- odoo.v_pos_line_full: vista enriquecida con linea_negocio_id y linea_negocio_nombre
- Vistas v_stock_by_product y v_stock_by_product_location (excluyen paneton/publicitario)

## Pending
- Odoo: Dar permisos lectura a User 111 sobre x_linea_negocio
- Re-ejecutar PRODUCTS sync FULL para poblar linea_negocio_id/linea_negocio
- Despliegue EasyPanel (BLOCKED)

## Backlog
- Refactoring: server.py -> separar endpoints sync control en Router dedicado
