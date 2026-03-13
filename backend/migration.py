"""
Odoo ODS Schema Migration - PostgreSQL DDL
Creates the full 'odoo' schema with all tables, indexes, views, and seed data.
"""

MIGRATION_SQL = """
-- ============================================================
-- A) EXTENSIONES
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- B) SCHEMA
-- ============================================================
CREATE SCHEMA IF NOT EXISTS odoo;

-- ============================================================
-- C) CONTROL DE SINCRONIZACIÓN
-- ============================================================

-- C1) odoo.sync_job
CREATE TABLE IF NOT EXISTS odoo.sync_job (
    job_code        TEXT PRIMARY KEY,
    enabled         BOOLEAN DEFAULT true,
    schedule_type   TEXT DEFAULT 'DAILY',
    run_time        TIME DEFAULT '23:00',
    priority        INT DEFAULT 10,
    mode            TEXT DEFAULT 'INCREMENTAL',
    chunk_size      INT DEFAULT 1000,
    company_scope   TEXT DEFAULT 'ALL',
    filters_json    JSONB NULL,
    last_run_at     TIMESTAMPTZ NULL,
    last_success_at TIMESTAMPTZ NULL,
    last_cursor     TIMESTAMPTZ NULL,
    last_error      TEXT NULL
);

-- C2) odoo.sync_run_log
CREATE TABLE IF NOT EXISTS odoo.sync_run_log (
    id              BIGSERIAL PRIMARY KEY,
    job_code        TEXT NOT NULL,
    company_key     TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ NULL,
    status          TEXT NOT NULL DEFAULT 'OK',
    rows_upserted   INT DEFAULT 0,
    rows_updated    INT DEFAULT 0,
    error_message   TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_run_log_job_company_started
    ON odoo.sync_run_log (job_code, company_key, started_at DESC);

-- ============================================================
-- D) MAESTROS
-- ============================================================

-- D1) odoo.res_company
CREATE TABLE IF NOT EXISTS odoo.res_company (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    name            TEXT,
    active          BOOLEAN,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

-- D2) odoo.res_users
CREATE TABLE IF NOT EXISTS odoo.res_users (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    login           TEXT,
    name            TEXT,
    active          BOOLEAN,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

-- D3) odoo.res_partner
CREATE TABLE IF NOT EXISTS odoo.res_partner (
    company_key             TEXT NOT NULL,
    odoo_id                 INT NOT NULL,
    name                    TEXT,
    display_name            TEXT,
    parent_id               INT NULL,
    commercial_partner_id   INT NULL,
    x_cliente_principal     INT NULL,
    x_es_principal          BOOLEAN NULL,
    mayorista               BOOLEAN NULL,
    x_no_llamar             BOOLEAN NULL,
    x_ultima_venta          TIMESTAMPTZ NULL,
    vat                     TEXT NULL,
    phone                   TEXT NULL,
    mobile                  TEXT NULL,
    street                  TEXT NULL,
    city                    TEXT NULL,
    active                  BOOLEAN,
    odoo_write_date         TIMESTAMPTZ,
    synced_at               TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_res_partner_cliente_principal
    ON odoo.res_partner (company_key, x_cliente_principal);
CREATE INDEX IF NOT EXISTS idx_res_partner_commercial
    ON odoo.res_partner (company_key, commercial_partner_id);
CREATE INDEX IF NOT EXISTS idx_res_partner_parent
    ON odoo.res_partner (company_key, parent_id);
CREATE INDEX IF NOT EXISTS idx_res_partner_active
    ON odoo.res_partner (company_key, active);
CREATE INDEX IF NOT EXISTS idx_res_partner_mayorista
    ON odoo.res_partner (company_key, mayorista);

-- ============================================================
-- E) PRODUCTOS
-- ============================================================

-- E1) odoo.product_template
CREATE TABLE IF NOT EXISTS odoo.product_template (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    name            TEXT,
    active          BOOLEAN,
    sale_ok         BOOLEAN,
    purchase_ok     BOOLEAN,
    list_price      NUMERIC(16,2),
    marca           TEXT NULL,
    tipo            TEXT NULL,
    tela            TEXT NULL,
    entalle         TEXT NULL,
    tel             TEXT NULL,
    hilo            TEXT NULL,
    linea_negocio   TEXT NULL,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_product_template_active
    ON odoo.product_template (company_key, active);
CREATE INDEX IF NOT EXISTS idx_product_template_sale_purchase
    ON odoo.product_template (company_key, sale_ok, purchase_ok);
CREATE INDEX IF NOT EXISTS idx_product_template_write_date
    ON odoo.product_template (company_key, odoo_write_date DESC);
CREATE INDEX IF NOT EXISTS idx_product_template_marca
    ON odoo.product_template (company_key, marca);
CREATE INDEX IF NOT EXISTS idx_product_template_tipo
    ON odoo.product_template (company_key, tipo);
CREATE INDEX IF NOT EXISTS idx_product_template_tela
    ON odoo.product_template (company_key, tela);
CREATE INDEX IF NOT EXISTS idx_product_template_entalle
    ON odoo.product_template (company_key, entalle);

-- E2) odoo.product_product
CREATE TABLE IF NOT EXISTS odoo.product_product (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    product_tmpl_id INT NOT NULL,
    barcode         TEXT NULL,
    active          BOOLEAN,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_product_product_tmpl
    ON odoo.product_product (company_key, product_tmpl_id);
CREATE INDEX IF NOT EXISTS idx_product_product_barcode
    ON odoo.product_product (company_key, barcode);

-- ============================================================
-- F) ATRIBUTOS TALLA / COLOR
-- ============================================================

-- F1) odoo.product_attribute
CREATE TABLE IF NOT EXISTS odoo.product_attribute (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    name            TEXT,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

-- F2) odoo.product_attribute_value
CREATE TABLE IF NOT EXISTS odoo.product_attribute_value (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    attribute_id    INT,
    name            TEXT,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_product_attr_value_attr
    ON odoo.product_attribute_value (company_key, attribute_id);

-- F3) odoo.product_template_attribute_line
CREATE TABLE IF NOT EXISTS odoo.product_template_attribute_line (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    product_tmpl_id INT,
    attribute_id    INT,
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_ptal_tmpl
    ON odoo.product_template_attribute_line (company_key, product_tmpl_id);
CREATE INDEX IF NOT EXISTS idx_ptal_attr
    ON odoo.product_template_attribute_line (company_key, attribute_id);

-- F4) odoo.product_attribute_value_product_product_rel
CREATE TABLE IF NOT EXISTS odoo.product_attribute_value_product_product_rel (
    company_key                 TEXT NOT NULL,
    product_product_id          INT NOT NULL,
    product_attribute_value_id  INT NOT NULL,
    PRIMARY KEY (company_key, product_product_id, product_attribute_value_id)
);

CREATE INDEX IF NOT EXISTS idx_pavppr_product
    ON odoo.product_attribute_value_product_product_rel (company_key, product_product_id);
CREATE INDEX IF NOT EXISTS idx_pavppr_value
    ON odoo.product_attribute_value_product_product_rel (company_key, product_attribute_value_id);

-- F5) Vista variantes flatten
CREATE OR REPLACE VIEW odoo.v_product_variant_flat AS
SELECT
    pp.company_key,
    pp.odoo_id          AS product_product_id,
    pp.product_tmpl_id,
    pp.barcode,
    talla_val.name       AS talla,
    color_val.name       AS color
FROM odoo.product_product pp
LEFT JOIN LATERAL (
    SELECT pav.name
    FROM odoo.product_attribute_value_product_product_rel rel
    JOIN odoo.product_attribute_value pav
        ON pav.company_key = rel.company_key
        AND pav.odoo_id = rel.product_attribute_value_id
    JOIN odoo.product_attribute pa
        ON pa.company_key = pav.company_key
        AND pa.odoo_id = pav.attribute_id
    WHERE rel.company_key = pp.company_key
      AND rel.product_product_id = pp.odoo_id
      AND pa.name IN ('TALLA','Talla','SIZE')
    LIMIT 1
) talla_val ON true
LEFT JOIN LATERAL (
    SELECT pav.name
    FROM odoo.product_attribute_value_product_product_rel rel
    JOIN odoo.product_attribute_value pav
        ON pav.company_key = rel.company_key
        AND pav.odoo_id = rel.product_attribute_value_id
    JOIN odoo.product_attribute pa
        ON pa.company_key = pav.company_key
        AND pa.odoo_id = pav.attribute_id
    WHERE rel.company_key = pp.company_key
      AND rel.product_product_id = pp.odoo_id
      AND pa.name IN ('COLOR','Color')
    LIMIT 1
) color_val ON true;

-- ============================================================
-- G) POS
-- ============================================================

-- G1) odoo.pos_order
CREATE TABLE IF NOT EXISTS odoo.pos_order (
    company_key         TEXT NOT NULL,
    odoo_id             INT NOT NULL,
    name                TEXT,
    date_order          TIMESTAMPTZ,
    partner_id          INT,
    user_id             INT,
    amount_total        NUMERIC(16,2),
    amount_tax          NUMERIC(16,2),
    state               TEXT,
    is_cancel           BOOLEAN NULL,
    order_cancel        BOOLEAN NULL,
    x_cliente_principal INT NULL,
    reserva             BOOLEAN NULL,
    reserva_use_id      INT NULL,
    odoo_write_date     TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_pos_order_date
    ON odoo.pos_order (company_key, date_order DESC);
CREATE INDEX IF NOT EXISTS idx_pos_order_partner
    ON odoo.pos_order (company_key, partner_id);
CREATE INDEX IF NOT EXISTS idx_pos_order_user
    ON odoo.pos_order (company_key, user_id);

-- G2) odoo.pos_order_line
CREATE TABLE IF NOT EXISTS odoo.pos_order_line (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    order_id        INT NOT NULL,
    product_id      INT NOT NULL,
    qty             NUMERIC(16,4),
    price_unit      NUMERIC(16,4),
    discount        NUMERIC(8,4),
    price_subtotal  NUMERIC(16,2),
    odoo_write_date TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_pos_order_line_order
    ON odoo.pos_order_line (company_key, order_id);
CREATE INDEX IF NOT EXISTS idx_pos_order_line_product
    ON odoo.pos_order_line (company_key, product_id);

-- ============================================================
-- H) VISTAS PARA FUTURO CRM
-- ============================================================

-- Drop dependent views first (order matters)
DROP VIEW IF EXISTS odoo.v_pos_line_full CASCADE;
DROP VIEW IF EXISTS odoo.v_pos_order_enriched CASCADE;

-- H1) v_partner_account_map
CREATE OR REPLACE VIEW odoo.v_partner_account_map AS
SELECT
    company_key,
    odoo_id AS contacto_partner_id,
    CASE
        WHEN x_cliente_principal IS NOT NULL THEN x_cliente_principal
        WHEN commercial_partner_id IS NOT NULL THEN commercial_partner_id
        WHEN parent_id IS NOT NULL THEN parent_id
        ELSE odoo_id
    END AS cuenta_partner_id
FROM odoo.res_partner;

-- H2) v_pos_order_enriched
CREATE OR REPLACE VIEW odoo.v_pos_order_enriched AS
SELECT
    po.company_key,
    po.odoo_id          AS odoo_order_id,
    po.date_order,
    po.partner_id       AS contacto_partner_id,
    COALESCE(po.x_cliente_principal, map.cuenta_partner_id) AS cuenta_partner_id,
    po.user_id,
    po.amount_total,
    po.state,
    po.reserva,
    po.reserva_use_id,
    (COALESCE(po.is_cancel, false) OR COALESCE(po.order_cancel, false)) AS is_cancelled
FROM odoo.pos_order po
LEFT JOIN odoo.v_partner_account_map map
    ON map.company_key = po.company_key
    AND map.contacto_partner_id = po.partner_id;

-- H3) v_pos_line_full (enriched lines for validation)
CREATE OR REPLACE VIEW odoo.v_pos_line_full AS
SELECT
    l.company_key,
    o.date_order,
    o.cuenta_partner_id,
    o.contacto_partner_id,
    o.user_id,
    o.state,
    o.is_cancelled,
    o.reserva,
    o.reserva_use_id,
    l.order_id,
    l.odoo_id           AS pos_order_line_id,
    l.product_id,
    l.qty,
    l.price_unit,
    l.discount,
    l.price_subtotal,
    vv.product_tmpl_id,
    vv.barcode,
    vv.talla,
    vv.color,
    pt.marca,
    pt.tipo,
    pt.tela,
    pt.entalle,
    pt.list_price,
    pt.linea_negocio_id,
    pt.linea_negocio    AS linea_negocio_nombre
FROM odoo.pos_order_line l
JOIN odoo.v_pos_order_enriched o
    ON o.company_key = l.company_key AND o.odoo_order_id = l.order_id
LEFT JOIN odoo.v_product_variant_flat vv
    ON vv.company_key = 'GLOBAL' AND vv.product_product_id = l.product_id
LEFT JOIN odoo.product_template pt
    ON pt.company_key = 'GLOBAL' AND pt.odoo_id = vv.product_tmpl_id;

-- ============================================================
-- ALTERACIONES: columnas audit (odoo_create_date, odoo_create_uid, odoo_write_uid)
-- ============================================================

-- res_partner
ALTER TABLE odoo.res_partner
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

ALTER TABLE odoo.res_partner
  ADD COLUMN IF NOT EXISTS state_name TEXT;

-- product_template
ALTER TABLE odoo.product_template
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

-- product_product
ALTER TABLE odoo.product_product
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

-- pos_order
ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS location_id INT;

ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS company_id INT;

ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS tipo_comp TEXT;

ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS num_comp TEXT;

ALTER TABLE odoo.pos_order
  ADD COLUMN IF NOT EXISTS x_pagos TEXT;

-- res_company (audit)
ALTER TABLE odoo.res_company
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

-- res_users (audit)
ALTER TABLE odoo.res_users
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

-- índices audit
CREATE INDEX IF NOT EXISTS idx_partner_create_date ON odoo.res_partner (company_key, odoo_create_date DESC);
CREATE INDEX IF NOT EXISTS idx_ptemplate_create_date ON odoo.product_template (company_key, odoo_create_date DESC);
CREATE INDEX IF NOT EXISTS idx_pos_order_create_date ON odoo.pos_order (company_key, odoo_create_date DESC);

-- ============================================================
-- STOCK LOCATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS odoo.stock_location (
    company_key     TEXT NOT NULL,
    odoo_id         INT NOT NULL,
    name            TEXT,
    x_nombre        TEXT,
    complete_name   TEXT,
    usage           TEXT,
    active          BOOLEAN,
    location_id     INT NULL,
    company_id      INT NULL,
    odoo_create_date TIMESTAMPTZ NULL,
    odoo_create_uid  INT NULL,
    odoo_write_date  TIMESTAMPTZ NULL,
    odoo_write_uid   INT NULL,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_location_usage ON odoo.stock_location (company_key, usage);
CREATE INDEX IF NOT EXISTS idx_stock_location_complete_name ON odoo.stock_location (company_key, complete_name);
CREATE INDEX IF NOT EXISTS idx_stock_location_parent ON odoo.stock_location (company_key, location_id);

-- ============================================================
-- STOCK QUANTS
-- ============================================================
CREATE TABLE IF NOT EXISTS odoo.stock_quant (
    company_key      TEXT NOT NULL,
    odoo_id          INT NOT NULL,
    product_id       INT NOT NULL,
    location_id      INT NOT NULL,
    qty              NUMERIC(16,4) NULL,
    reserved_qty     NUMERIC(16,4) NULL,
    in_date          TIMESTAMPTZ NULL,
    odoo_create_date TIMESTAMPTZ NULL,
    odoo_create_uid  INT NULL,
    odoo_write_date  TIMESTAMPTZ NULL,
    odoo_write_uid   INT NULL,
    synced_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_quant_product ON odoo.stock_quant (company_key, product_id);
CREATE INDEX IF NOT EXISTS idx_stock_quant_location ON odoo.stock_quant (company_key, location_id);
CREATE INDEX IF NOT EXISTS idx_stock_quant_prod_loc ON odoo.stock_quant (company_key, product_id, location_id);

-- ============================================================
-- J) CREDIT INVOICES (account.invoice con is_credit=True)
-- ============================================================

-- X_LINEA_NEGOCIO master table
CREATE TABLE IF NOT EXISTS odoo.x_linea_negocio (
    company_key      TEXT NOT NULL,
    odoo_id          INT NOT NULL,
    name             TEXT NULL,
    odoo_create_date TIMESTAMPTZ NULL,
    odoo_create_uid  INT NULL,
    odoo_write_date  TIMESTAMPTZ NULL,
    odoo_write_uid   INT NULL,
    synced_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

-- Add linea_negocio_id (integer FK) to product_template
ALTER TABLE odoo.product_template
  ADD COLUMN IF NOT EXISTS linea_negocio_id INT NULL;

ALTER TABLE odoo.product_template
  ADD COLUMN IF NOT EXISTS linea_negocio TEXT NULL;

-- J1) odoo.account_invoice_credit (cabecera)
CREATE TABLE IF NOT EXISTS odoo.account_invoice_credit (
    company_key      TEXT NOT NULL,
    odoo_id          INT NOT NULL,
    number           TEXT NULL,
    date_invoice     DATE NULL,
    partner_id       INT NULL,
    user_id          INT NULL,
    company_id       INT NULL,
    state            TEXT NULL,
    amount_total     NUMERIC(16,2) NULL,
    amount_residual  NUMERIC(16,2) NULL,
    payment_term_id  INT NULL,
    currency_id      INT NULL,
    odoo_create_date TIMESTAMPTZ NULL,
    odoo_create_uid  INT NULL,
    odoo_write_date  TIMESTAMPTZ NULL,
    odoo_write_uid   INT NULL,
    synced_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_credit_inv_partner   ON odoo.account_invoice_credit (company_key, partner_id);
CREATE INDEX IF NOT EXISTS idx_credit_inv_date      ON odoo.account_invoice_credit (company_key, date_invoice);
CREATE INDEX IF NOT EXISTS idx_credit_inv_state     ON odoo.account_invoice_credit (company_key, state);

-- J2) odoo.account_invoice_credit_line (líneas)
CREATE TABLE IF NOT EXISTS odoo.account_invoice_credit_line (
    company_key      TEXT NOT NULL,
    odoo_id          INT NOT NULL,
    invoice_id       INT NOT NULL,
    product_id       INT NULL,
    name             TEXT NULL,
    quantity         NUMERIC(16,4) NULL,
    price_unit       NUMERIC(16,4) NULL,
    discount         NUMERIC(16,4) NULL,
    price_subtotal   NUMERIC(16,2) NULL,
    odoo_create_date TIMESTAMPTZ NULL,
    odoo_create_uid  INT NULL,
    odoo_write_date  TIMESTAMPTZ NULL,
    odoo_write_uid   INT NULL,
    synced_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (company_key, odoo_id)
);

CREATE INDEX IF NOT EXISTS idx_credit_inv_line_invoice  ON odoo.account_invoice_credit_line (company_key, invoice_id);
CREATE INDEX IF NOT EXISTS idx_credit_inv_line_product  ON odoo.account_invoice_credit_line (company_key, product_id);

-- ============================================================
-- I) STOCK VIEWS (after tables exist)
-- ============================================================

-- I1) v_stock_by_product_location (internal active locations only, with product info)
DROP VIEW IF EXISTS odoo.v_stock_by_product CASCADE;
DROP VIEW IF EXISTS odoo.v_stock_by_product_location CASCADE;

CREATE OR REPLACE VIEW odoo.v_stock_by_product_location AS
SELECT
    sq.product_id,
    sq.location_id,
    pt.name  AS product_name,
    pt.marca,
    pt.tipo,
    COALESCE(pt.active, true) AS active,
    SUM(sq.qty)          AS qty,
    SUM(sq.reserved_qty) AS reserved_qty,
    SUM(sq.qty) - SUM(sq.reserved_qty) AS available_qty
FROM odoo.stock_quant sq
JOIN odoo.stock_location sl
    ON sl.company_key = 'GLOBAL' AND sl.odoo_id = sq.location_id
LEFT JOIN odoo.product_product pp
    ON pp.company_key = 'GLOBAL' AND pp.odoo_id = sq.product_id
LEFT JOIN odoo.product_template pt
    ON pt.company_key = 'GLOBAL' AND pt.odoo_id = pp.product_tmpl_id
WHERE sq.company_key = 'GLOBAL'
  AND sl.usage = 'internal'
  AND COALESCE(sl.active, true) = true
  AND pt.name NOT ILIKE '%paneton%'
  AND pt.name NOT ILIKE '%publicitario%'
GROUP BY sq.product_id, sq.location_id, pt.name, pt.marca, pt.tipo, pt.active;

-- I2) v_stock_by_product (aggregated across all internal locations, with product info)
CREATE OR REPLACE VIEW odoo.v_stock_by_product AS
SELECT
    product_id,
    product_name,
    marca,
    tipo,
    active,
    SUM(qty)          AS qty,
    SUM(reserved_qty) AS reserved_qty,
    SUM(available_qty) AS available_qty
FROM odoo.v_stock_by_product_location
GROUP BY product_id, product_name, marca, tipo, active;

-- ============================================================
-- SEED: Insertar jobs base (idempotente)
-- ============================================================
INSERT INTO odoo.sync_job (job_code, run_time, priority)
VALUES
    ('RES_COMPANY',      '23:00', 10),
    ('STOCK_LOCATIONS',  '23:08', 15),
    ('RES_USERS',        '23:02', 20),
    ('RES_PARTNER',      '23:05', 30),
    ('PRODUCTS',         '23:10', 40),
    ('ATTRIBUTES',       '23:12', 50),
    ('POS_ORDERS',       '23:20', 60)
ON CONFLICT (job_code) DO NOTHING;

INSERT INTO odoo.sync_job (job_code, enabled, schedule_type, run_time, priority, mode, chunk_size, company_scope)
VALUES ('STOCK_QUANTS', true, 'HOURLY', '23:15', 17, 'INCREMENTAL', 5000, 'GLOBAL')
ON CONFLICT (job_code) DO UPDATE SET
    schedule_type = 'HOURLY',
    chunk_size = 5000,
    company_scope = 'GLOBAL';

INSERT INTO odoo.sync_job (job_code, enabled, schedule_type, run_time, priority, mode, chunk_size, company_scope)
VALUES ('AR_CREDIT_INVOICES', true, 'DAILY', '23:40', 70, 'INCREMENTAL', 2000, 'MULTI')
ON CONFLICT (job_code) DO NOTHING;

INSERT INTO odoo.sync_job (job_code, enabled, schedule_type, run_time, priority, mode, chunk_size, company_scope)
VALUES ('X_LINEA_NEGOCIO', true, 'DAILY', '23:09', 35, 'INCREMENTAL', 500, 'GLOBAL')
ON CONFLICT (job_code) DO NOTHING;
"""

# List of all odoo tables (for status queries)
ODOO_TABLES = [
    "sync_job",
    "sync_run_log",
    "res_company",
    "res_users",
    "res_partner",
    "x_linea_negocio",
    "stock_location",
    "stock_quant",
    "product_template",
    "product_product",
    "product_attribute",
    "product_attribute_value",
    "product_template_attribute_line",
    "product_attribute_value_product_product_rel",
    "pos_order",
    "pos_order_line",
    "account_invoice_credit",
    "account_invoice_credit_line",
]

ODOO_VIEWS = [
    "v_product_variant_flat",
    "v_partner_account_map",
    "v_pos_order_enriched",
    "v_pos_line_full",
    "v_stock_by_product_location",
    "v_stock_by_product",
]
