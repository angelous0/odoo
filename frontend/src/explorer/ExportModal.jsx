import { useEffect, useMemo, useState } from "react";
import { X, Download, ChevronRight, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

function Chip({ label, on, onClick }) {
  return (
    <div
      onClick={onClick}
      className="inline-flex items-center gap-[7px] px-[10px] py-[6px] rounded-lg cursor-pointer border"
      style={{ borderColor: on ? "var(--primaryBorder)" : "var(--border)", background: on ? "var(--primaryWeak)" : "var(--surface)" }}
    >
      <span
        className="w-[17px] h-[17px] rounded-[4px] flex items-center justify-center flex-none"
        style={{ border: `1.5px solid ${on ? "var(--primary)" : "var(--border2)"}`, background: on ? "var(--primary)" : "transparent" }}
      >
        {on && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>}
      </span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "11px" }}>{label}</span>
    </div>
  );
}

export default function ExportModal({ table, defaultTable, onClose }) {
  const exportTableName = defaultTable || table.name;
  const [fmtType, setFmtType] = useState("csv");
  const [curCols, setCurCols] = useState([]);
  const [curSel, setCurSel] = useState(new Set());
  const [relTables, setRelTables] = useState([]); // [{table, via, cols:[], sel:Set, expanded}]
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.get("/schema/table-columns", { params: { table: exportTableName } }).then((res) => {
      const names = (res.data.columns || []).map((c) => c.name);
      setCurCols(names);
      setCurSel(new Set(names));
    });
    api.get("/schema/relations").then((res) => {
      const meta = res.data.tables?.[exportTableName];
      const refs = meta?.refs || [];
      setRelTables(refs.map(([t, via]) => ({ table: t, via, cols: [], sel: new Set(), expanded: false, loaded: false })));
    });
  }, [exportTableName]);

  const toggleCur = (c) => setCurSel((s) => { const n = new Set(s); n.has(c) ? n.delete(c) : n.add(c); return n; });
  const presetCur = (all) => setCurSel(all ? new Set(curCols) : new Set());

  const toggleRelExpand = async (idx) => {
    setRelTables((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], expanded: !next[idx].expanded };
      return next;
    });
    const rt = relTables[idx];
    if (!rt.loaded) {
      const res = await api.get("/schema/table-columns", { params: { table: rt.table } });
      const names = (res.data.columns || []).map((c) => c.name);
      setRelTables((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], cols: names, loaded: true };
        return next;
      });
    }
  };

  const toggleRelCol = (idx, c) => {
    setRelTables((prev) => {
      const next = [...prev];
      const sel = new Set(next[idx].sel);
      sel.has(c) ? sel.delete(c) : sel.add(c);
      next[idx] = { ...next[idx], sel };
      return next;
    });
  };

  const totalRelCols = relTables.reduce((a, t) => a + t.sel.size, 0);
  const totalRelTables = relTables.filter((t) => t.sel.size > 0).length;

  const doExport = async () => {
    setDownloading(true);
    try {
      const body = {
        table: exportTableName,
        format: fmtType,
        columns: Array.from(curSel),
        related: relTables.filter((t) => t.sel.size > 0).map((t) => ({ table: t.table, columns: Array.from(t.sel) })),
        limit: 5000,
      };
      const res = await api.post("/export", body, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${exportTableName}.${fmtType}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      onClose();
    } catch (e) {
      toast.error("Error al exportar");
    }
    setDownloading(false);
  };

  return (
    <div className="absolute inset-0 z-[71]">
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,.34)" }} onClick={onClose} />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[720px] max-w-[calc(100%-40px)] max-h-[86%] rounded-[15px] border flex flex-col overflow-hidden"
        style={{ background: "var(--surface)", borderColor: "var(--border)", boxShadow: "var(--shadow)" }}
      >
        <div className="flex-none px-5 py-[15px] border-b flex items-start justify-between gap-3" style={{ borderColor: "var(--border)" }}>
          <div>
            <div className="flex items-center gap-[9px]">
              <Download size={16} style={{ color: "var(--primary)" }} />
              <span style={{ fontWeight: 700, fontSize: "15px" }}>Exportar</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "12px", color: "var(--muted)" }}>{exportTableName}</span>
            </div>
            <div className="mt-1" style={{ fontSize: "11px", color: "var(--muted)" }}>Elige las columnas a incluir</div>
          </div>
          <div className="flex items-center gap-[10px]">
            <div className="flex gap-[2px] p-[3px] rounded-lg border" style={{ background: "var(--card2)", borderColor: "var(--border)" }}>
              {[["csv", "CSV plano"], ["json", "JSON anidado"]].map(([v, l]) => (
                <span
                  key={v}
                  onClick={() => setFmtType(v)}
                  className="inline-flex items-center h-[27px] px-3 rounded-md cursor-pointer"
                  style={{ fontSize: "11px", fontWeight: 700, background: fmtType === v ? "var(--surface)" : "transparent", color: fmtType === v ? "var(--fg)" : "var(--muted)" }}
                >
                  {l}
                </span>
              ))}
            </div>
            <button onClick={onClose} className="w-7 h-7 rounded-lg border flex items-center justify-center" style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--muted)" }}>
              <X size={14} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto px-5 py-4">
          <div className="flex items-center justify-between mb-[10px]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: "var(--primary)" }} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "12px" }}>{exportTableName}</span>
              <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted2)" }}>tabla actual · {curSel.size} sel.</span>
            </div>
            <div className="flex gap-[6px]">
              <span onClick={() => presetCur(true)} className="cursor-pointer px-[10px] py-1 rounded-md border" style={{ fontSize: "10.5px", fontWeight: 600, color: "var(--primaryText)", borderColor: "var(--primaryBorder)", background: "var(--primaryWeak)" }}>Todas</span>
              <span onClick={() => presetCur(false)} className="cursor-pointer px-[10px] py-1 rounded-md border" style={{ fontSize: "10.5px", fontWeight: 600, color: "var(--muted)", borderColor: "var(--border)" }}>Ninguna</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mb-[22px]">
            {curCols.map((c) => <Chip key={c} label={c} on={curSel.has(c)} onClick={() => toggleCur(c)} />)}
          </div>

          {relTables.length > 0 && (
            <>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)", marginBottom: 4 }}>
                Traer de tablas relacionadas
              </div>
              <div className="mb-[11px]" style={{ fontSize: "10.5px", color: "var(--muted)" }}>Entra a cada tabla y marca qué columnas unir a la exportación.</div>
              {relTables.map((rt, idx) => (
                <div key={rt.table} className="rounded-[10px] border mb-2 overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
                  <div onClick={() => toggleRelExpand(idx)} className="flex items-center gap-[9px] px-[13px] py-[10px] cursor-pointer">
                    {rt.expanded ? <ChevronDown size={12} style={{ color: "var(--muted2)" }} /> : <ChevronRight size={12} style={{ color: "var(--muted2)" }} />}
                    <span className="w-[7px] h-[7px] rounded-full" style={{ background: "var(--primary)" }} />
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "12px" }}>{rt.table}</span>
                    <span style={{ fontSize: "10px", color: "var(--muted2)" }}>via {rt.via}</span>
                    <span className="ml-auto" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "10px", color: "var(--primaryText)" }}>{rt.sel.size} / {rt.cols.length || "…"}</span>
                  </div>
                  {rt.expanded && (
                    <div className="flex flex-wrap gap-2 px-[34px] pb-[14px]">
                      {rt.cols.map((c) => <Chip key={c} label={c} on={rt.sel.has(c)} onClick={() => toggleRelCol(idx, c)} />)}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>

        <div className="flex-none px-5 py-[13px] border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: "var(--fg)" }}>{curSel.size + totalRelCols}</span> columnas ·{" "}
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: "var(--fg)" }}>{totalRelTables}</span> tablas relacionadas
          </span>
          <button
            disabled={downloading || curSel.size === 0}
            onClick={doExport}
            className="h-[35px] px-4 flex items-center gap-2 rounded-lg disabled:opacity-50"
            style={{ background: "var(--primary)", color: "#fff", fontWeight: 700, fontSize: "12.5px", border: "none" }}
          >
            <Download size={14} />
            Descargar {fmtType === "csv" ? "CSV" : "JSON"}
          </button>
        </div>
      </div>
    </div>
  );
}
