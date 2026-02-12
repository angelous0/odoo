# Odoo ODS Schema Manager - PRD

## Problem Statement
Create PostgreSQL schema "odoo" as ODS (Operational Data Store) to mirror Odoo ERP data for future CRM/Finance/Production use. Multi-company support, idempotent upserts, sync control infrastructure.

## Architecture
- **Backend**: FastAPI + psycopg2 → PostgreSQL (external: 72.60.241.216:9090/datos)
- **Frontend**: React + Tailwind + shadcn/ui (dark theme, Spanish UI)
- **Database**: PostgreSQL schema `odoo` with 13 tables, 3 views, 38 indexes

## What's Implemented (2026-02-12)
- **Schema `odoo`** created with pgcrypto extension
- **Sync Control**: sync_job (6 base jobs seeded), sync_run_log
- **Maestros**: res_company, res_users, res_partner (with custom x_cliente_principal fields)
- **Productos**: product_template, product_product (with all custom fields: marca, tipo, tela, entalle, tel, hilo)
- **Atributos**: product_attribute, product_attribute_value, product_template_attribute_line, product_attribute_value_product_product_rel
- **POS**: pos_order, pos_order_line
- **Vistas**: v_product_variant_flat (talla/color flatten), v_partner_account_map, v_pos_order_enriched
- **38 indexes** for common queries
- **Auto-migration on startup** + manual re-execute endpoint
- **Dashboard UI**: Panel de Migración with metrics, tables list, sync jobs, indexes, and logs page

## User Personas
- Database Administrators managing Odoo-to-PostgreSQL sync
- Data Architects designing the ODS layer

## Core Requirements (Static)
- Multi-empresa: company_key TEXT NOT NULL on all tables
- PK: (company_key, odoo_id) on all entity tables
- Idempotent: UNIQUE(company_key, odoo_id) + ON CONFLICT DO NOTHING for seeds
- Common fields: odoo_id, odoo_write_date, synced_at

## Backlog
### P0 (Done)
- [x] Schema creation
- [x] All 13 tables with correct columns
- [x] All indexes
- [x] All 3 views
- [x] Seed sync_jobs
- [x] Admin panel UI

### P1 (Next)
- [ ] Actual Odoo API connector for data sync
- [ ] Sync execution engine (run jobs)
- [ ] CRM schema (phase 2)

### P2
- [ ] Schedule management UI (edit job schedules)
- [ ] Real-time sync monitoring
- [ ] Data quality checks/validation
