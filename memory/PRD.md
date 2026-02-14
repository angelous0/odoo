# Odoo ODS - Product Requirements Document

## Problema Original
Crear un ODS en PostgreSQL para replicar datos de Odoo 10 via XML-RPC.

## Arquitectura
- **Backend:** FastAPI + PostgreSQL (psycopg2) + XML-RPC (Odoo 10)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Sync:** Motor incremental/completa con scheduler (DAILY/HOURLY)

## Fases Completadas (1-5): Todas

## Cambios recientes (14 Feb 2026)

### Fix: Campos resumen en productos
- **tipo**: usa `x_tipo_resumen` de product.tipo
- **entalle**: usa `x_entalle` de product.entalle
- **tela**: usa `x_tela` de product.tela

### Fix: Resiliencia del sync ante 502
- OdooClient: 6 reintentos con backoff exponencial (max 60s), reconexión en 502/503
- POS sync: manejo de errores por batch con 3 reintentos (30s entre cada uno)
- Pausa de 0.3s entre batches para reducir carga en Odoo
- Resultado: Ambission completó 129,200 órdenes sin interrupción pese a múltiples 502

## Endpoints API
- POST /api/sync/run, GET /api/sync/status, GET /api/health
- GET /api/pos-lines-full, GET /api/stock-quants
- GET /api/stock-by-product, GET /api/stock-by-location
- GET /api/stock-locations, POST /api/migrate

## Estado: Proyecto funcionalmente completo
