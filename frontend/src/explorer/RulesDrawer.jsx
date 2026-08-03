import { useEffect, useState } from "react";
import { X, Star } from "lucide-react";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { POS_LINE_REAL } from "@/lib/tables";

const RULE_DEFS = [
  { n: 1, t: "Sin líneas canceladas", d: "Excluye líneas con is_cancelled = true." },
  { n: 2, t: "Sin reservas", d: "Excluye líneas y órdenes marcadas como reserva." },
  { n: 3, t: "Sin reservas usadas", d: "Reserva ya usada en otra orden (reserva_use_id ≠ 0)." },
  { n: 4, t: "Sin órdenes canceladas", d: "Excluye órdenes completas con order_cancel = true." },
  { n: 5, t: "Anti doble-conteo NV + Factura", d: "NV (done) con factura espejo — mismo monto, tienda y cliente ±7 días → solo cuenta la facturada." },
  { n: 6, t: "Sin productos prohibidos", d: "Excluye \"basura\" de Odoo y productos que no son venta.", chips: ["correa", "bolsa", "panetón", "probador", "saco", "lapicero", "publicitario", "envío", "tallero"] },
  { n: 7, t: "Sin excluidos de Producción", d: "Productos con estado = 'excluido' en la clasificación de Producción." },
];

export default function RulesDrawer({ onClose }) {
  const [enabled, setEnabled] = useState(() => Object.fromEntries(RULE_DEFS.map((r) => [r.n, true])));
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/venta-real/rule-counts").then((res) => setStats(res.data)).catch(() => setStats(null));
  }, []);

  const countFor = (n) => (stats?.rules || []).find((r) => r.n === n)?.count ?? null;
  const netExcluded = RULE_DEFS.reduce((a, r) => (enabled[r.n] ? a + (countFor(r.n) || 0) : a), 0);

  return (
    <div className="absolute inset-0 z-[60]">
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,.28)" }} onClick={onClose} />
      <div
        className="absolute top-0 right-0 bottom-0 w-[400px] flex flex-col border-l"
        style={{ background: "var(--surface)", borderColor: "var(--border)", boxShadow: "var(--shadow)" }}
      >
        <div className="flex-none px-[18px] py-[15px] border-b flex items-start justify-between gap-[10px]" style={{ borderColor: "var(--border)" }}>
          <div>
            <div className="flex items-center gap-2">
              <Star size={15} fill="var(--primary)" style={{ color: "var(--primary)" }} />
              <span style={{ fontWeight: 700, fontSize: "14px" }}>Reglas de "venta real"</span>
            </div>
            <div className="mt-1" style={{ fontSize: "11px", color: "var(--muted)" }}>
              Se aplican en el DB · vista <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--primaryText)" }}>{POS_LINE_REAL}</span>
            </div>
          </div>
          <button onClick={onClose} className="flex-none w-7 h-7 rounded-lg border flex items-center justify-center" style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--muted)" }}>
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 overflow-auto px-4 py-3">
          {RULE_DEFS.map((r) => {
            const on = enabled[r.n];
            const count = countFor(r.n);
            return (
              <div key={r.n} className="py-[11px] border-b flex gap-3 items-start" style={{ borderColor: "var(--border)" }}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-[7px]">
                    <span
                      className="rounded-[5px] px-[5px] py-[1px] border"
                      style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9px", color: "var(--muted2)", background: "var(--card2)", borderColor: "var(--border)" }}
                    >
                      R{r.n}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: "12px" }}>{r.t}</span>
                  </div>
                  <div className="mt-1" style={{ fontSize: "10.5px", lineHeight: 1.45, color: "var(--muted)" }}>{r.d}</div>
                  {r.chips && (
                    <div className="flex flex-wrap gap-1 mt-[7px]">
                      {r.chips.map((c) => (
                        <span key={c} className="rounded px-[6px] py-[1px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "9px", fontWeight: 600, color: "var(--danger)", background: "var(--dangerWeak)" }}>{c}</span>
                      ))}
                    </div>
                  )}
                  <div className="mt-[7px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "10px", fontWeight: 600, color: "var(--danger)" }}>
                    − {count === null ? "…" : fmt(count)} filas excluidas
                  </div>
                </div>
                <div
                  onClick={() => setEnabled((s) => ({ ...s, [r.n]: !s[r.n] }))}
                  className="flex-none mt-[2px] cursor-pointer relative"
                  style={{ width: 34, height: 19, borderRadius: 999, background: on ? "var(--primary)" : "var(--border2)" }}
                >
                  <span className="absolute rounded-full bg-white" style={{ top: 2, left: on ? 17 : 2, width: 15, height: 15, boxShadow: "0 1px 2px rgba(0,0,0,.35)" }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex-none px-[18px] py-[13px] border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
            Neto excluido: <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: "var(--danger)" }}>{fmt(netExcluded)}</span> filas
          </span>
          <button onClick={onClose} className="h-[31px] px-[15px] rounded-lg" style={{ background: "var(--primary)", color: "#fff", fontWeight: 700, fontSize: "12px", border: "none" }}>
            Aplicar
          </button>
        </div>
      </div>
    </div>
  );
}
