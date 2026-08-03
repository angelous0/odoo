import { useState } from "react";
import { Search, RefreshCw } from "lucide-react";
import { short } from "@/lib/format";

function StatusDot({ table }) {
  const color = !table.exists ? "var(--danger)" : "var(--primary)";
  return <span className="w-[7px] h-[7px] rounded-full flex-none inline-block" style={{ background: color }} />;
}

export default function TablesRail({ grouped, selTable, onSelect, totalCount, errorCount, syncing, onSyncAll, loading }) {
  const [filter, setFilter] = useState("");
  const q = filter.trim().toLowerCase();

  return (
    <div
      className="flex-none w-[272px] border-r flex flex-col min-h-0"
      style={{ borderColor: "var(--border)", background: "var(--bg)" }}
    >
      <div className="p-3 pb-2">
        <div className="relative">
          <Search size={14} className="absolute left-[10px] top-1/2 -translate-y-1/2" style={{ color: "var(--muted2)" }} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrar tablas…"
            className="w-full h-[31px] rounded-lg pl-[31px] pr-2 outline-none border"
            style={{ background: "var(--surface)", borderColor: "var(--border)", fontSize: "11.5px", fontWeight: 500, color: "var(--fg)" }}
          />
        </div>
      </div>
      <div className="flex-1 overflow-auto pb-2">
        {loading ? (
          <div className="px-4 py-6 text-center text-xs" style={{ color: "var(--muted2)" }}>
            Cargando…
          </div>
        ) : (
          grouped.map((g) => {
            const items = q
              ? g.items.filter((t) => t.name.toLowerCase().includes(q) || t.label.toLowerCase().includes(q))
              : g.items;
            if (items.length === 0) return null;
            return (
              <div key={g.group}>
                <div className="px-4 pt-[11px] pb-1 flex items-center justify-between">
                  <span
                    className="flex items-center gap-1"
                    style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".09em", textTransform: "uppercase", color: "var(--muted2)" }}
                  >
                    {g.group === "Favoritos" && "★ "}
                    {g.group}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "9.5px", color: "var(--muted2)" }}>
                    {g.items.length}
                  </span>
                </div>
                {items.map((t) => {
                  const on = t.name === selTable;
                  return (
                    <div
                      key={t.name}
                      onClick={() => onSelect(t.name)}
                      title={t.label}
                      className="flex items-center gap-2 mx-[7px] my-[1px] px-[9px] py-[6px] rounded-[7px] cursor-pointer"
                      style={{
                        borderLeft: on ? "2px solid var(--primary)" : "2px solid transparent",
                        background: on ? "var(--sel)" : "transparent",
                      }}
                      onMouseEnter={(e) => { if (!on) e.currentTarget.style.background = "var(--rowHover)"; }}
                      onMouseLeave={(e) => { if (!on) e.currentTarget.style.background = "transparent"; }}
                    >
                      <StatusDot table={t} />
                      <span
                        className="flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap"
                        style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "11.5px" }}
                      >
                        {t.name}
                      </span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500, fontSize: "10px", color: "var(--muted2)" }}>
                        {t.type === "VIEW" ? `~${short(t.row_count)}` : short(t.row_count)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
      <div className="flex-none border-t px-3 py-[10px] flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
        <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)" }}>
          {totalCount} objetos
          {errorCount > 0 && <span style={{ color: "var(--danger)" }}> · {errorCount} con error</span>}
        </span>
        <button
          onClick={onSyncAll}
          disabled={syncing}
          title="Sincronizar todas las tablas desde Odoo"
          className="flex items-center gap-[6px] h-7 px-[10px] rounded-[7px] border"
          style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--fg)", fontSize: "10.5px", fontWeight: 600 }}
        >
          <RefreshCw size={12} className={syncing ? "animate-spin" : ""} />
          Sincronizar todo
        </button>
      </div>
    </div>
  );
}
