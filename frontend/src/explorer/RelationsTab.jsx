import { Download } from "lucide-react";
import { fmt } from "@/lib/format";
import { Badge } from "@/components/DataGrid";

function RelCard({ label, via, onClick }) {
  return (
    <div
      onClick={onClick}
      className="rounded-[10px] border cursor-pointer px-3 py-[10px]"
      style={{ minWidth: 190, maxWidth: 230, background: "var(--card)", borderColor: "var(--border)" }}
    >
      <div className="flex items-center gap-[7px]">
        <span className="w-[7px] h-[7px] rounded-full flex-none" style={{ background: "var(--primary)" }} />
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "11.5px" }}>{label}</span>
      </div>
      <div className="mt-1 pl-[14px]" style={{ fontSize: "10px", color: "var(--muted2)" }}>
        via <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--muted)" }}>{via}</span>
      </div>
    </div>
  );
}

export default function RelationsTab({ table, onNavigate, onExportRelated }) {
  const refs = table.refs || [];
  const refBy = table.ref_by || [];
  const hasRel = refs.length > 0 || refBy.length > 0;

  if (!hasRel) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="text-center py-16" style={{ color: "var(--muted2)", fontSize: "12.5px" }}>
          Sin relaciones registradas para <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{table.name}</span>.
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto px-6 pt-[18px] pb-7">
      <div className="flex items-center justify-between gap-[10px] mb-[6px]">
        <p style={{ fontSize: "11.5px", color: "var(--muted)" }}>
          Mapa de relaciones de <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)", fontWeight: 600 }}>{table.name}</span> · clic en cualquier tabla para navegar
        </p>
        <span style={{ fontSize: "10.5px", fontWeight: 600, color: "var(--muted2)" }}>N:1 = referencia a · 1:N = referenciada por</span>
      </div>

      {table.from && table.from.length > 0 && (
        <div className="my-[10px] mb-5 px-[14px] py-[11px] rounded-[10px] border" style={{ background: "var(--card2)", borderColor: "var(--border)" }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)", marginBottom: 9 }}>
            Vista derivada de
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {table.from.map((f) => (
              <span
                key={f}
                onClick={() => onNavigate(f)}
                className="inline-flex items-center gap-[6px] px-[10px] py-[5px] rounded-lg border cursor-pointer"
                style={{ background: "var(--surface)", borderColor: "var(--border)", fontFamily: "'JetBrains Mono', monospace", fontSize: "11px", fontWeight: 600 }}
              >
                <span className="w-[7px] h-[7px] rounded-full" style={{ background: "var(--primary)" }} />
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid items-center gap-[30px] mt-[14px]" style={{ gridTemplateColumns: "1fr auto 1fr" }}>
        <div className="flex flex-col gap-3 items-end">
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted2)" }}>
            Referencia a · N:1
          </div>
          {refs.map(([t, via]) => (
            <div key={t + via} className="flex items-center w-full justify-end">
              <RelCard label={t} via={via} onClick={() => onNavigate(t)} />
              <div className="flex-none w-[34px] h-[2px] relative" style={{ background: "linear-gradient(90deg,var(--border2),var(--primary))" }}>
                <span className="absolute -right-px -top-1" style={{ color: "var(--primary)", fontSize: 11 }}>▶</span>
              </div>
            </div>
          ))}
        </div>

        <div
          className="text-center rounded-[13px] border-2 px-[22px] py-4"
          style={{ background: "var(--primaryWeak)", borderColor: "var(--primary)", minWidth: 200, boxShadow: "var(--shadow)" }}
        >
          <Badge kind={table.type === "VIEW" ? "amber" : "emerald"}>{table.type}</Badge>
          <div className="mt-2" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "14px", color: "var(--primaryText)" }}>{table.name}</div>
          <div className="mt-1" style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)" }}>
            {fmt(table.row_count)} filas · {table.col_count} col
          </div>
        </div>

        <div className="flex flex-col gap-3 items-start">
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted2)" }}>
            Referenciada por · 1:N
          </div>
          {refBy.length === 0 && (
            <div className="px-[14px] py-[10px] rounded-[10px] border border-dashed" style={{ borderColor: "var(--border2)", fontSize: "11px", color: "var(--muted2)" }}>
              Ninguna — es una hoja del grafo
            </div>
          )}
          {refBy.map(([t, via]) => (
            <div key={t + via} className="flex items-center w-full">
              <div className="flex-none w-[34px] h-[2px] relative" style={{ background: "linear-gradient(90deg,var(--primary),var(--border2))" }}>
                <span className="absolute -left-px -top-1" style={{ color: "var(--primary)", fontSize: 11 }}>◀</span>
              </div>
              <RelCard label={t} via={via} onClick={() => onNavigate(t)} />
            </div>
          ))}
        </div>
      </div>

      <div className="mt-[22px] px-[14px] py-[11px] rounded-[10px] border flex items-center gap-[10px]" style={{ background: "var(--card2)", borderColor: "var(--border)" }}>
        <Download size={15} style={{ color: "var(--primary)" }} />
        <span className="flex-1" style={{ fontSize: "11.5px", color: "var(--muted)" }}>Exporta esta tabla junto con las conectadas en un solo archivo.</span>
        <button
          onClick={onExportRelated}
          className="h-[30px] px-3 rounded-lg border"
          style={{ background: "var(--primaryWeak)", borderColor: "var(--primaryBorder)", color: "var(--primaryText)", fontWeight: 700, fontSize: "11px" }}
        >
          Exportar con relaciones
        </button>
      </div>
    </div>
  );
}
