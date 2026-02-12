# Odoo ODS Schema Manager - PRD

## Problem Statement
Create PostgreSQL schema "odoo" as ODS (Operational Data Store) to mirror Odoo 10 ERP data via XML-RPC. Multi-company support, incremental sync by write_date, scheduled cron, batch upserts.

## Architecture
- **Backend**: FastAPI + psycopg2 → PostgreSQL (72.60.241.216:9090/datos)
- **Sync**: XML-RPC client → Odoo 10 (ambission.app-gestion.net)
- **Frontend**: React + Tailwind + shadcn/ui (dark theme, Spanish UI)
- **Database**: PostgreSQL schema `odoo` with 13 tables, 3 views, 41 indexes

## What's Implemented

### Phase 1 (2026-02-12): Schema DDL
- Schema `odoo` + pgcrypto extension
- 13 tables: sync_job, sync_run_log, res_company, res_users, res_partner, product_template, product_product, product_attribute, product_attribute_value, product_template_attribute_line, product_attribute_value_product_product_rel, pos_order, pos_order_line
- 3 views: v_product_variant_flat, v_partner_account_map, v_pos_order_enriched
- 41 indexes, 6 seed sync_jobs
- Audit columns: odoo_create_date, odoo_create_uid, odoo_write_uid on 6 tables

### Phase 2 (2026-02-12): Sync Engine
- Odoo 10 XML-RPC client with retry (3x) + backoff
- SyncService: masters (GLOBAL) + POS (Ambission/ProyectoModa)
- ID-based pagination (stable, no loops)
- Batch upserts via execute_values (high performance)
- Advisory lock to prevent concurrent syncs
- Scheduler (every 60s, matches job run_time)
- **1.25M+ rows synced**: 118K POS orders, 1M+ order lines, 11K partners, 32K products, 65K variant-attribute rels

## Data Summary
| Table | Rows |
|---|---|
| pos_order_line | 1,019,656 |
| pos_order | 118,576 |
| product_attribute_value_product_product_rel | 65,190 |
| product_product | 32,657 |
| res_partner | 11,592 |
| product_template | 2,040 |
| product_attribute_value | 432 |
| res_users | 65 |
| product_attribute | 15 |
| res_company | 2 |

## Backlog
### P0 (Done)
- [x] Schema creation + DDL
- [x] XML-RPC client + sync engine
- [x] Batch upserts + ID pagination
- [x] POS multi-company (Ambission + ProyectoModa)
- [x] Scheduler
- [x] Admin panel UI with sync buttons

### P1 (Next)
- [ ] CRM schema (phase 3)
- [ ] Sync monitoring dashboard (charts, timelines)
- [ ] Job schedule editing in UI

### P2
- [ ] Data quality validation
- [ ] Webhook-triggered sync
- [ ] Historical sync performance metrics
