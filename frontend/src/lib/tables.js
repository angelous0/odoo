// Tablas de líneas POS: par vista-completa / vista-real para el toggle "Venta real".
export const POS_LINE_TABLES = new Set(["pos_order_line", "v_pos_line_full", "v_pos_line_real"]);
export const POS_LINE_FULL = "v_pos_line_full";
export const POS_LINE_REAL = "v_pos_line_real";

export function isPosLineTable(name) {
  return POS_LINE_TABLES.has(name);
}

// Columnas por defecto mostradas para las tablas de líneas POS (14), basadas en las
// columnas reales de v_pos_line_full/v_pos_line_real (migration.py) — no inventadas.
export const POS_LINE_COLUMNS = [
  { key: "date_order", label: "Fecha", align: "left", width: 100, sortable: true },
  { key: "company_key", label: "Empresa", align: "left", width: 90 },
  { key: "tipo_comp", label: "Comprob.", align: "left", width: 100 },
  { key: "order_id", label: "Orden", align: "right", width: 78, sortable: true },
  { key: "state", label: "Estado", align: "left", width: 90 },
  { key: "vendedor_name", label: "Vendedor", align: "left", width: 110 },
  { key: "marca", label: "Marca", align: "left", width: 100 },
  { key: "tipo", label: "Tipo", align: "left", width: 90 },
  { key: "tela", label: "Tela", align: "left", width: 90 },
  { key: "talla", label: "Talla", align: "left", width: 56 },
  { key: "color", label: "Color", align: "left", width: 76 },
  { key: "qty", label: "Qty", align: "right", width: 56, sortable: true },
  { key: "price_unit", label: "P.Unit", align: "right", width: 82, sortable: true },
  { key: "price_subtotal", label: "Subtotal", align: "right", width: 96, sortable: true },
];

export const POS_LINE_DETAIL_GROUPS = [
  { h: "Venta", fields: ["date_order", "company_key", "tipo_comp", "num_comp", "state", "vendedor_name", "x_pagos"] },
  { h: "Producto", fields: ["marca", "tipo", "tela", "talla", "color", "entalle", "barcode"] },
  { h: "Montos", fields: ["qty", "price_unit", "discount", "price_subtotal", "list_price"] },
];

export const POS_LINE_FKS = [
  { table: "pos_order", field: "order_id", label: "order_id" },
  { table: "product_product", field: "product_id", label: "producto" },
  { table: "res_partner", field: "cuenta_partner_id", label: "cliente" },
  { table: "res_users", field: "vendedor_id", label: "vendedor" },
  { table: "res_company", field: "company_id", label: "empresa" },
];

export const FIELD_LABELS = {
  date_order: "Fecha", company_key: "Empresa", tipo_comp: "Tipo comp.", num_comp: "N° comprobante",
  order_id: "Orden", state: "Estado", vendedor_name: "Vendedor", x_pagos: "Pagos",
  marca: "Marca", tipo: "Tipo", tela: "Tela", talla: "Talla", color: "Color", entalle: "Entalle", barcode: "Barcode",
  qty: "Cantidad", price_unit: "Precio unit.", discount: "Descuento %", price_subtotal: "Subtotal", list_price: "Precio lista",
};

export const NUMERIC_FIELDS = new Set(["qty", "price_unit", "discount", "price_subtotal", "list_price", "order_id"]);
