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
- **POS:** Ordenes y lineas con vista enriquecida (v_pos_line_full), location_id
- **Stock:** Quants, ubicaciones, vistas por producto y por tienda
- **Facturas de Credito:** Sincronizacion completa con lineas
- **x_linea_negocio:** Tabla maestra sincronizada desde Odoo

### Filtros de Catalogo (Feb 2026)
- **Exclusion "paneton" y "publicitario":** Filtro `NOT ILIKE` en vistas SQL
- **Toggle archivados:** Parametro `include_archived` en endpoints stock
- **Sync incluye archivados:** `active_test: False`

### Sync Control (Mar 2026)
- Pagina Sync Control con monitor de jobs, badges de estado, botones Run
- Botones macro: Clientes, Ventas, Productos (X_LINEA_NEGOCIO+PRODUCTS+ATTRIBUTES), Stock, Creditos
- Endpoints: GET /api/odoo-sync/job-status, POST /api/odoo-sync/run, POST /api/odoo-sync/run-batch
- Background execution con polling y toast notifications

### Cambios Mar 11 2026
- **Nueva tabla x_linea_negocio:** Tabla maestra sincronizada (id, name, audit fields)
- **Nuevo job X_LINEA_NEGOCIO:** Prioridad 35, antes de PRODUCTS
- **Campos linea_negocio_id + linea_negocio en product_template:** ID entero y nombre texto
- **Fix purchase_ok:** Eliminado filtro `('purchase_ok','=',False)` que excluia productos validos

## Endpoints API
- `POST /api/migrate` - Migracion idempotente
- `POST /api/sync/run` - Ejecutar sincronizacion
- `GET /api/sync/status` - Estado de jobs
- `GET /api/stock-by-product` - Stock por producto (include_archived, only_available)
- `GET /api/stock-by-location` - Stock por tienda
- `GET /api/pos-lines-full` - Lineas POS enriquecidas
- `GET /api/credit-invoices` - Facturas de credito
- `GET /api/health` - Health check
- `POST /api/sync/pos` - Sync POS con metricas (protegido por token)
- `GET /api/odoo-sync/job-status` - Estado de todos los jobs
- `POST /api/odoo-sync/run` - Ejecutar job individual
- `POST /api/odoo-sync/run-batch` - Ejecutar batch de jobs

## Schema DB (key tables)
- `odoo.product_template` - Productos con tipo, entalle, tela, active, linea_negocio_id, linea_negocio
- `odoo.x_linea_negocio` - Tabla maestra de lineas de negocio
- `odoo.stock_quant` - Quants de stock
- `odoo.res_partner` - Partners con state_name, phone, mobile
- `odoo.pos_order` - Ordenes POS con location_id
- Vistas v_stock_by_product y v_stock_by_product_location (excluyen paneton/publicitario)

## Pending Issues
- P0: Despliegue EasyPanel - BLOCKED (usuario debe configurar permisos Odoo + redesplegar)
- Odoo Permission: User 111 necesita acceso lectura a modelo x_linea_negocio
- PRODUCTS sync necesita re-ejecutarse para limpiar estado ERROR

## Backlog
- Refactoring: Mover endpoints sync control a FastAPI Router separado
