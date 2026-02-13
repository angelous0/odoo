# Odoo ODS - Product Requirements Document

## Problema Original
Crear un Operational Data Store (ODS) en PostgreSQL para replicar datos de Odoo 10 via XML-RPC.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Sync:** Motor incremental/completa con scheduler (DAILY/HOURLY)

## Fases Completadas (1-5)
- Schema odoo, sync engine, stock locations, UI, stock actual (1M+ quants)

## Fix: Campos resumen en productos (13 Feb 2026)
- **tipo**: usa `x_tipo_resumen` de product.tipo (ej: "Bermuda Cargo" → "Short Denim")
- **entalle**: usa `x_entalle` de product.entalle (ej: "Regular Fit" → "Regular", "Slim Fit" → "Slim")
- **tela**: usa `x_tela` de product.tela (ej: "Jersey 24/1" → "Algodón", "Polelina" → "Popelina")
- Función genérica `_load_resumen_map` y `_resolve` para los 3 campos
- Vistas SQL de stock incluyen product_name, marca, tipo via JOINs

## Endpoints API
- POST /api/sync/run, GET /api/sync/status, GET /api/health
- GET /api/pos-lines-full, GET /api/stock-quants
- GET /api/stock-by-product, GET /api/stock-by-location
- GET /api/stock-locations, POST /api/migrate

## Estado: Proyecto funcionalmente completo
