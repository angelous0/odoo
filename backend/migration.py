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
    (COALESCE(po.is_cancel, false) OR COALESCE(po.order_cancel, false)) AS is_cancelled
FROM odoo.pos_order po
LEFT JOIN odoo.v_partner_account_map map
    ON map.company_key = po.company_key
    AND map.contacto_partner_id = po.partner_id;

-- ============================================================
-- ALTERACIONES: columnas audit (odoo_create_date, odoo_create_uid, odoo_write_uid)
-- ============================================================

-- res_partner
ALTER TABLE odoo.res_partner
  ADD COLUMN IF NOT EXISTS odoo_create_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS odoo_create_uid INT,
  ADD COLUMN IF NOT EXISTS odoo_write_uid INT;

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
-- SEED: Insertar jobs base (idempotente)
-- ============================================================
INSERT INTO odoo.sync_job (job_code, run_time, priority)
VALUES
    ('RES_COMPANY',  '23:00', 10),
    ('RES_USERS',    '23:02', 20),
    ('RES_PARTNER',  '23:05', 30),
    ('PRODUCTS',     '23:10', 40),
    ('ATTRIBUTES',   '23:12', 50),
    ('POS_ORDERS',   '23:20', 60)
ON CONFLICT (job_code) DO NOTHING;
"""

# List of all odoo tables (for status queries)
ODOO_TABLES = [
    "sync_job",
    "sync_run_log",
    "res_company",
    "res_users",
    "res_partner",
    "product_template",
    "product_product",
    "product_attribute",
    "product_attribute_value",
    "product_template_attribute_line",
    "product_attribute_value_product_product_rel",
    "pos_order",
    "pos_order_line",
]

ODOO_VIEWS = [
    "v_product_variant_flat",
    "v_partner_account_map",
    "v_pos_order_enriched",
]
