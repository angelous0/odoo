import { X, Link2, ChevronRight } from "lucide-react";
import { fmt, fmt2, abs } from "@/lib/format";
import { POS_LINE_DETAIL_GROUPS, POS_LINE_FKS, FIELD_LABELS, NUMERIC_FIELDS } from "@/lib/tables";
import { useGotoTable } from "@/lib/nav";

function fmtVal(key, v) {
  if (v === null || v === undefined || v === "") return "—";
  if (key === "date_order" || (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v))) return abs(v);
  if (NUMERIC_FIELDS.has(key)) return Number.isInteger(v) ? fmt(v) : fmt2(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

export default function RowDetailDrawer({ table, row, posTable, onClose }) {
  const gotoTable = useGotoTable();
  const groups = posTable
    ? POS_LINE_DETAIL_GROUPS.map((g) => ({ h: g.h, rows: g.fields.filter((f) => f in row).map((f) => ({ k: FIELD_LABELS[f] || f, v: fmtVal(f, row[f]) })) }))
    : [{ h: "Datos", rows: Object.keys(row).map((f) => ({ k: f, v: fmtVal(f, row[f]) })) }];

  const fks = posTable
    ? POS_LINE_FKS.filter((fk) => fk.field in row && row[fk.field] != null)
    : (table.refs || []).filter(([, via]) => via in row && row[via] != null).map(([t, via]) => ({ table: t, field: via, label: via }));

  const title = row.marca && row.tipo ? `${row.marca} · ${row.tipo}` : table.name;
  const pk = row.pos_order_line_id ?? row.odoo_id ?? "";

  return (
    <div className="absolute inset-0 z-[60]">
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,.28)" }} onClick={onClose} />
      <div
        className="absolute top-0 right-0 bottom-0 w-[404px] flex flex-col border-l"
        style={{ background: "var(--surface)", borderColor: "var(--border)", boxShadow: "var(--shadow)" }}
      >
        <div className="flex-none px-[18px] py-[15px] border-b flex items-start justify-between gap-[10px]" style={{ borderColor: "var(--border)" }}>
          <div className="min-w-0">
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)" }}>
              Detalle de fila
            </div>
            <div className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap" style={{ fontWeight: 700, fontSize: "15px" }}>{title}</div>
            {pk !== "" && <div className="mt-[2px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "11px", color: "var(--muted)" }}>{pk}</div>}
          </div>
          <button onClick={onClose} className="flex-none w-7 h-7 rounded-lg border flex items-center justify-center" style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--muted)" }}>
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 overflow-auto px-[18px] py-[14px]">
          {groups.map((g) => (
            <div key={g.h}>
              <div className="mt-3 mb-[6px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)" }}>
                {g.h}
              </div>
              {g.rows.map((r) => (
                <div key={r.k} className="flex items-baseline justify-between gap-[14px] py-[5px] border-b" style={{ borderColor: "var(--border)" }}>
                  <span className="flex-none" style={{ fontSize: "11px", color: "var(--muted)" }}>{r.k}</span>
                  <span className="overflow-hidden text-ellipsis whitespace-nowrap text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "11.5px" }}>{r.v}</span>
                </div>
              ))}
            </div>
          ))}
          {fks.length > 0 && (
            <>
              <div className="mt-4 mb-[7px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)" }}>
                Ir a tabla relacionada
              </div>
              {fks.map((fk) => (
                <div
                  key={fk.table + fk.field}
                  onClick={() => gotoTable(fk.table)}
                  className="flex items-center gap-[9px] px-[10px] py-2 mb-[6px] rounded-lg border cursor-pointer"
                  style={{ borderColor: "var(--border)", background: "var(--card2)" }}
                >
                  <Link2 size={14} style={{ color: "var(--primary)" }} />
                  <div className="flex-1 min-w-0">
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "11.5px" }}>{fk.table}</div>
                    <div style={{ fontSize: "10px", color: "var(--muted2)" }}>{fk.label}: {row[fk.field]}</div>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--muted2)" }} />
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
