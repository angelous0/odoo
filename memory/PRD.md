# Odoo ODS - Product Requirements Document

## Problema Original
Crear un ODS en PostgreSQL para replicar datos de Odoo 10 via XML-RPC.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Sync:** Motor incremental/completa con scheduler (DAILY/HOURLY)

## Módulos Sincronizados
1. res_company, res_users, res_partner (GLOBAL)
2. product_template, product_product, attributes (GLOBAL)
3. stock_location, stock_quant (GLOBAL, HOURLY)
4. pos_order, pos_order_line (MULTI: Ambission + ProyectoModa)
5. **account_invoice_credit + lines** (MULTI: Ambission + ProyectoModa) - NEW 15 Feb 2026

## Cambios recientes

### 15 Feb 2026: Módulo de Créditos
- DDL: `odoo.account_invoice_credit` + `odoo.account_invoice_credit_line` con índices
- Sync Job: `AR_CREDIT_INVOICES` (DAILY 23:40, INCREMENTAL, chunk_size=2000, MULTI)
- Domain: `[('is_credit','=',True), ('type','=','out_invoice')]`
- Campos: number, date_invoice, partner_id, state, amount_total, amount_residual, etc.
- Líneas: invoice_id, product_id, name, quantity, price_unit, discount, price_subtotal
- Endpoints: GET /api/credit-invoices, GET /api/credit-invoice-lines
- Frontend: Página Créditos con filtros (empresa, fecha, estado) y paginación
- Sync FULL: Ambission 108,903 rows + ProyectoModa 7,788 rows = 5,390 facturas + 111,301 líneas
- Scheduler: MULTI_JOBS soportado en scheduler.py

### 14 Feb 2026: Campos resumen + Resiliencia 502
- tipo/entalle/tela usan x_tipo_resumen/x_entalle/x_tela
- OdooClient con 6 reintentos, backoff exponencial, reconexión en 502/503
- POS sync con retry por batch

## Endpoints API
- POST /api/sync/run, GET /api/sync/status, GET /api/health
- GET /api/pos-lines-full, GET /api/stock-quants
- GET /api/stock-by-product, GET /api/stock-by-location
- GET /api/credit-invoices, GET /api/credit-invoice-lines
- GET /api/stock-locations, POST /api/migrate

## Estado: Proyecto funcionalmente completo
