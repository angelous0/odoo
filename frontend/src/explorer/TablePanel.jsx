import { useEffect, useState } from "react";
import { Share2, Download, RefreshCw, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { fmt, ago, abs } from "@/lib/format";
import { Badge } from "@/components/DataGrid";
import { api } from "@/lib/api";
import DataTab from "@/explorer/DataTab";
import ColumnsTab from "@/explorer/ColumnsTab";
import RelationsTab from "@/explorer/RelationsTab";
import ExportModal from "@/explorer/ExportModal";
import { isPosLineTable, POS_LINE_FULL, POS_LINE_REAL } from "@/lib/tables";

export default function TablePanel({ table, onNavigate, onRefreshMeta }) {
  const [tab, setTab] = useState("datos");
  const [exportOpen, setExportOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    setExportOpen(false);
  }, [table?.name]);

  if (!table) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: "var(--surface)" }}>
        <span style={{ color: "var(--muted2)" }}>Cargando…</span>
      </div>
    );
  }

  const relCount = (table.refs?.length || 0) + (table.ref_by?.length || 0);
  const posTable = isPosLineTable(table.name);
  const exportTable = posTable ? (table.name === "pos_order_line" ? POS_LINE_FULL : table.name) : table.name;

  const refreshTable = async () => {
    setRefreshing(true);
    try {
      await api.post("/sync/run", { target: "ALL" });
      toast.success("Sincronización disparada");
    } catch (e) {
      toast.error("Error al sincronizar");
    }
    onRefreshMeta();
    setRefreshing(false);
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 relative" style={{ background: "var(--surface)" }}>
      {/* HEADER */}
      <div className="flex-none px-6 pt-[15px] border-b" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-[10px] flex-wrap">
              <h2 style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "19px", letterSpacing: "-.01em" }}>
                {table.name}
              </h2>
              <Badge kind={table.type === "VIEW" ? "amber" : "emerald"}>{table.type}</Badge>
              <span style={{ fontSize: "12.5px", fontWeight: 500, color: "var(--muted)" }}>{table.label}</span>
            </div>
            <div className="flex items-center gap-2 mt-[7px] flex-wrap" style={{ fontSize: "11.5px", fontWeight: 500, color: "var(--muted)" }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)", fontWeight: 600 }}>
                {table.type === "VIEW" ? `~${fmt(table.row_count)}` : fmt(table.row_count)}
              </span>
              <span>filas</span>
              <span style={{ color: "var(--border2)" }}>·</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)", fontWeight: 600 }}>{table.col_count}</span>
              <span>columnas</span>
              {table.last_sync_at && (
                <>
                  <span style={{ color: "var(--border2)" }}>·</span>
                  <span>última sync</span>
                  <span style={{ color: "var(--primary)", fontWeight: 700 }}>hace {ago(table.last_sync_at)}</span>
                  <span style={{ color: "var(--muted2)", fontFamily: "'JetBrains Mono', monospace", fontSize: "10.5px" }}>
                    {abs(table.last_sync_at)}
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="flex-none flex items-center gap-2">
            <HeaderButton icon={<Share2 size={13} style={{ color: "var(--primary)" }} />} onClick={() => setTab("relaciones")}>
              {relCount}
            </HeaderButton>
            <HeaderButton icon={<Download size={13} />} onClick={() => setExportOpen(true)}>
              Exportar
              <ChevronDown size={11} style={{ color: "var(--muted2)" }} />
            </HeaderButton>
            <HeaderButton icon={<RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />} onClick={refreshTable}>
              Actualizar
            </HeaderButton>
          </div>
        </div>
        <div className="flex gap-[3px] mt-[14px]">
          {[
            { key: "datos", label: "Datos" },
            { key: "columnas", label: "Columnas" },
            { key: "relaciones", label: "Relaciones" },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-[15px] py-[9px] rounded-t-lg"
              style={{
                border: "none",
                borderBottom: tab === t.key ? "2px solid var(--primary)" : "2px solid transparent",
                fontSize: "12.5px",
                fontWeight: tab === t.key ? 700 : 600,
                background: "transparent",
                color: tab === t.key ? "var(--fg)" : "var(--muted)",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "datos" && <DataTab table={table} onOpenDetail={() => {}} />}
      {tab === "columnas" && <ColumnsTab table={table} />}
      {tab === "relaciones" && <RelationsTab table={table} onNavigate={onNavigate} onExportRelated={() => setExportOpen(true)} />}

      {exportOpen && <ExportModal table={table} defaultTable={exportTable} onClose={() => setExportOpen(false)} />}
    </div>
  );
}

function HeaderButton({ icon, children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="h-[31px] px-[11px] flex items-center gap-[6px] rounded-lg border"
      style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--fg)", fontSize: "11.5px", fontWeight: 600 }}
    >
      {icon}
      {children}
    </button>
  );
}
