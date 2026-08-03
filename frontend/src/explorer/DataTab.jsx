import { useEffect, useMemo, useState } from "react";
import { Search, Plus, X, Columns as ColumnsIcon, ChevronDown, ChevronLeft, ChevronRight, Star, AlertTriangle, RefreshCw } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/api";
import DataGrid from "@/components/DataGrid";
import RowDetailDrawer from "@/explorer/RowDetailDrawer";
import RulesDrawer from "@/explorer/RulesDrawer";
import { fmt, fmt2, abs } from "@/lib/format";
import {
  isPosLineTable, POS_LINE_FULL, POS_LINE_REAL, POS_LINE_COLUMNS, FIELD_LABELS, NUMERIC_FIELDS,
} from "@/lib/tables";

const PAGE_SIZE = 50;
const TEXT_OPS = [["es", "es (=)"], ["contains", "contiene"], ["neq", "no es (≠)"]];
const NUM_OPS = [["eq", "="], ["neq", "≠"], ["gt", ">"], ["lt", "<"], ["gte", "≥"], ["lte", "≤"]];
const OP_SYM = { es: "=", contains: "∋", neq: "≠", eq: "=", gt: ">", lt: "<", gte: "≥", lte: "≤" };

export default function DataTab({ table }) {
  const posTable = isPosLineTable(table.name);
  const queryTable = posTable ? undefined : table.name; // resolved below via view state

  const [view, setView] = useState("real");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState([]);
  const [sort, setSort] = useState({ key: null, dir: "desc" });
  const [page, setPage] = useState(1);
  const [visibleCols, setVisibleCols] = useState(null); // null => all/default
  const [colsOpen, setColsOpen] = useState(false);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [detailRow, setDetailRow] = useState(null);
  const [rulesOpen, setRulesOpen] = useState(false);

  const [data, setData] = useState({ rows: [], total: 0, total_pages: 0, columns: [], error: null });
  const [loading, setLoading] = useState(true);
  const [availCols, setAvailCols] = useState([]);

  const effectiveTable = posTable ? (view === "real" ? POS_LINE_REAL : POS_LINE_FULL) : table.name;

  useEffect(() => {
    setPage(1);
    setFilters([]);
    setSearch("");
    setSort({ key: null, dir: "desc" });
    setDetailRow(null);
    setRulesOpen(false);
    setVisibleCols(null);
  }, [table.name]);

  useEffect(() => {
    if (!table.exists) { setLoading(false); return; }
    setLoading(true);
    const params = { table: effectiveTable, page, page_size: PAGE_SIZE };
    if (search.trim()) params.search = search.trim();
    if (sort.key) { params.sort = sort.key; params.dir = sort.dir; }
    if (filters.length) params.filters = JSON.stringify(filters.map((f) => ({ field: f.field, op: f.op, value: f.value })));
    api
      .get("/table-data", { params })
      .then((res) => {
        setData(res.data);
        if (res.data.columns) setAvailCols(res.data.columns);
      })
      .catch(() => setData({ rows: [], total: 0, total_pages: 0, columns: [], error: "network" }))
      .finally(() => setLoading(false));
  }, [effectiveTable, page, search, sort, filters, table.exists]);

  const fieldOptions = useMemo(() => {
    if (posTable) return POS_LINE_COLUMNS.map((c) => c.key);
    return availCols;
  }, [posTable, availCols]);

  const cols = useMemo(() => {
    if (posTable) {
      const base = visibleCols ? POS_LINE_COLUMNS.filter((c) => visibleCols.has(c.key)) : POS_LINE_COLUMNS;
      return base.map((c) => ({ ...c, sortDir: sort.key === c.key ? sort.dir : null }));
    }
    const list = visibleCols ? availCols.filter((c) => visibleCols.has(c)) : availCols;
    return list.map((c) => ({
      key: c, label: c, align: NUMERIC_FIELDS.has(c) ? "right" : "left", width: "flex",
      sortable: true, sortDir: sort.key === c ? sort.dir : null,
    }));
  }, [posTable, visibleCols, availCols, sort]);

  const rows = useMemo(() => {
    return (data.rows || []).map((r, i) => {
      const excluded = view === "full" && (r.is_cancelled || r.reserva || (r.reserva_use_id && r.reserva_use_id !== 0));
      const cells = cols.map((c) => renderCell(c.key, r, posTable));
      return { key: r.pos_order_line_id ?? r.odoo_id ?? i, onClick: () => setDetailRow(r), highlight: excluded, cells };
    });
  }, [data.rows, cols, posTable, view]);

  const activeFilters = filters;

  if (!table.exists) {
    return (
      <div className="flex-1 overflow-auto p-6">
        <div
          className="rounded-xl p-[26px] flex gap-4 items-start border"
          style={{ borderColor: "var(--danger)", background: "var(--dangerWeak)" }}
        >
          <AlertTriangle size={26} style={{ color: "var(--danger)" }} className="flex-none mt-[2px]" />
          <div className="flex-1">
            <div style={{ fontWeight: 700, fontSize: "15px" }}>No se pudo cargar {table.name}</div>
            <div className="mt-[5px]" style={{ fontSize: "12.5px", lineHeight: 1.55, color: "var(--muted)", maxWidth: 560 }}>
              Esta tabla o vista no existe en el schema, o falló al sincronizarse. Revisa el Registro de cargas.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* filter bar */}
      <div className="flex-none relative px-6 py-[11px] flex items-center gap-[9px] flex-wrap border-b" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
        <div className="relative flex-none w-[214px]">
          <Search size={14} className="absolute left-[10px] top-1/2 -translate-y-1/2" style={{ color: "var(--muted2)" }} />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Buscar en la tabla…"
            className="w-full h-[30px] rounded-lg pl-[30px] pr-2 outline-none border"
            style={{ background: "var(--surface)", borderColor: "var(--border)", fontSize: "11.5px", fontWeight: 500, color: "var(--fg)" }}
          />
        </div>

        {posTable && (
          <>
            <Pill active={view === "real"} onClick={() => { setView("real"); setPage(1); }}>
              <Star size={12} fill="currentColor" className="mr-[5px]" />Venta real
            </Pill>
            <Pill active={view === "full"} onClick={() => { setView("full"); setPage(1); }}>Todo</Pill>
            <span className="w-px h-5" style={{ background: "var(--border)" }} />
          </>
        )}

        <Popover open={builderOpen} onOpenChange={setBuilderOpen}>
          <PopoverTrigger asChild>
            <button
              className="inline-flex items-center gap-[6px] h-[30px] px-[11px] rounded-lg border border-dashed"
              style={{ borderColor: "var(--border2)", background: "var(--surface)", color: "var(--fg)", fontSize: "11px", fontWeight: 600 }}
            >
              <Plus size={12} style={{ color: "var(--primary)" }} />Filtro
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-[300px] p-0" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
            <FilterBuilder fields={fieldOptions} onAdd={(f) => { setFilters((prev) => [...prev, { ...f, id: `${Date.now()}` }]); setBuilderOpen(false); setPage(1); }} />
          </PopoverContent>
        </Popover>

        {activeFilters.map((f) => (
          <span
            key={f.id}
            className="inline-flex items-center gap-[7px] h-[30px] pl-[11px] pr-2 rounded-lg"
            style={{ background: "var(--primaryWeak)", border: "1px solid var(--primaryBorder)", color: "var(--primaryText)", fontFamily: "'JetBrains Mono', monospace", fontSize: "11px", fontWeight: 600 }}
          >
            {FIELD_LABELS[f.field] || f.field} {OP_SYM[f.op] || f.op} {f.value}
            <span
              className="cursor-pointer opacity-70"
              onClick={() => { setFilters((prev) => prev.filter((x) => x.id !== f.id)); setPage(1); }}
            >
              <X size={12} />
            </span>
          </span>
        ))}
        {(activeFilters.length > 0 || search.trim()) && (
          <span
            className="cursor-pointer px-1"
            style={{ fontSize: "11px", fontWeight: 600, color: "var(--muted)" }}
            onClick={() => { setFilters([]); setSearch(""); setPage(1); }}
          >
            Limpiar
          </span>
        )}

        <div className="ml-auto relative">
          <Popover open={colsOpen} onOpenChange={setColsOpen}>
            <PopoverTrigger asChild>
              <button
                className="inline-flex items-center gap-[6px] h-[30px] px-[11px] rounded-lg border"
                style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--fg)", fontSize: "11px", fontWeight: 600 }}
              >
                <ColumnsIcon size={13} style={{ color: "var(--muted2)" }} />
                Columnas · {cols.length}/{posTable ? POS_LINE_COLUMNS.length : availCols.length}
                <ChevronDown size={11} style={{ color: "var(--muted2)" }} />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-[242px] p-[11px]" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
              <ColumnsSelector
                allCols={posTable ? POS_LINE_COLUMNS.map((c) => ({ key: c.key, label: c.label })) : availCols.map((c) => ({ key: c, label: c }))}
                visibleCols={visibleCols}
                onChange={setVisibleCols}
              />
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {posTable && view === "real" && <VentaRealBanner onOpenRules={() => setRulesOpen(true)} />}
      {posTable && view === "full" && (
        <div className="flex-none mx-6 mt-3 px-[13px] py-[9px] flex items-center gap-[11px] rounded-[9px]" style={{ background: "var(--warnWeak)", border: "1px solid var(--warnBorder)" }}>
          <AlertTriangle size={15} style={{ color: "var(--warn)" }} className="flex-none" />
          <div className="flex-1 min-w-0" style={{ fontSize: "11.5px", lineHeight: 1.4 }}>
            Mostrando <span style={{ fontWeight: 700, color: "var(--warn)" }}>todo</span> ({POS_LINE_FULL}) · incluye canceladas y reservas <span style={{ color: "var(--muted)" }}>— marcadas en rojo</span>
          </div>
          <span className="flex-none cursor-pointer px-[9px] py-1 rounded-md" style={{ fontWeight: 700, fontSize: "11px", color: "var(--primaryText)", border: "1px solid var(--primaryBorder)", background: "var(--surface)" }} onClick={() => setView("real")}>
            Volver a venta real
          </span>
        </div>
      )}

      <div className="flex-1 overflow-auto px-6 pt-[14px] pb-2 min-h-0">
        {loading ? (
          <div className="flex justify-center py-10"><RefreshCw size={18} className="animate-spin" style={{ color: "var(--muted2)" }} /></div>
        ) : (
          <DataGrid
            cols={cols}
            rows={rows}
            onSort={(key) => setSort((s) => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }))}
            minWidth={Math.max(560, cols.reduce((a, c) => a + (c.width === "flex" ? 160 : c.width), 0))}
            emptyLabel="Sin resultados con estos filtros."
          />
        )}
      </div>

      <div className="flex-none px-6 py-2 flex items-center justify-between" style={{ fontSize: "11px", fontWeight: 500, color: "var(--muted)" }}>
        <span>
          Mostrando <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)" }}>{fmt(data.rows.length)}</span> filas de{" "}
          <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)" }}>{fmt(data.total)}</span>
        </span>
        <div className="flex items-center gap-[6px]">
          <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>Pág {page} / {Math.max(1, data.total_pages)}</span>
          <PageBtn disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={13} /></PageBtn>
          <PageBtn disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)}><ChevronRight size={13} /></PageBtn>
        </div>
      </div>

      {detailRow && <RowDetailDrawer table={table} row={detailRow} posTable={posTable} onClose={() => setDetailRow(null)} />}
      {rulesOpen && <RulesDrawer onClose={() => setRulesOpen(false)} />}
    </>
  );
}

function renderCell(key, r, posTable) {
  const v = r[key];
  if (posTable) {
    if (key === "company_key") return { value: v, badge: v === "Ambission" ? "emerald" : "neutral" };
    if (key === "state") return r.is_cancelled ? { value: "CANCEL", badge: "danger" } : { value: v, tone: "muted" };
    if (key === "date_order") return { value: abs(v), tone: "muted" };
    if (key === "order_id") return { value: v, tone: "primary" };
    if (key === "qty") return { value: fmt(v) };
    if (key === "price_unit" || key === "list_price") return { value: fmt2(v), tone: "muted" };
    if (key === "price_subtotal") return { value: fmt2(v), strong: true };
    if (key === "vendedor_name" || key === "tipo_comp") return { value: v || "—", tone: "muted" };
    if (key === "marca" || key === "tipo" || key === "tela") return { value: v || "—", tone: "muted" };
  }
  if (typeof v === "number") return { value: Number.isInteger(v) ? fmt(v) : fmt2(v), align: "right" };
  if (typeof v === "boolean") return { value: v ? "true" : "false", tone: "muted" };
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) return { value: abs(v), tone: "muted" };
  return { value: v ?? "—" };
}

function Pill({ active, onClick, children }) {
  return (
    <span
      onClick={onClick}
      className="inline-flex items-center h-[30px] px-[11px] rounded-lg cursor-pointer select-none"
      style={{
        fontSize: "11px", fontWeight: 700,
        background: active ? "var(--primary)" : "var(--surface)",
        color: active ? "#fff" : "var(--muted)",
        border: active ? "1px solid var(--primary)" : "1px solid var(--border)",
      }}
    >
      {children}
    </span>
  );
}

function PageBtn({ disabled, onClick, children }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="w-[26px] h-[26px] rounded-md border flex items-center justify-center disabled:opacity-40"
      style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--fg)" }}
    >
      {children}
    </button>
  );
}

function VentaRealBanner({ onOpenRules }) {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.get("/venta-real/rule-counts").then((res) => setStats(res.data)).catch(() => setStats(null));
  }, []);
  return (
    <div className="flex-none mx-6 mt-3 px-[13px] py-[9px] flex items-center gap-[11px] rounded-[9px]" style={{ background: "var(--primaryWeak)", border: "1px solid var(--primaryBorder)" }}>
      <Star size={15} fill="var(--primary)" style={{ color: "var(--primary)" }} className="flex-none" />
      <div className="flex-1 min-w-0" style={{ fontSize: "11.5px", lineHeight: 1.4 }}>
        <span style={{ fontWeight: 700, color: "var(--primaryText)" }}>Venta real</span> · usando{" "}
        <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--primaryText)" }}>{POS_LINE_REAL}</span>
        {stats && (
          <>
            {" · "}
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>{fmt(stats.real)}</span> de{" "}
            <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{fmt(stats.universe)}</span> filas ·{" "}
            <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--danger)" }}>{fmt(stats.net_excluded)}</span> excluidas por{" "}
            <span style={{ fontWeight: 600 }}>7/7 reglas</span>
          </>
        )}
      </div>
      <span
        className="flex-none cursor-pointer px-[9px] py-1 rounded-md"
        style={{ fontWeight: 700, fontSize: "11px", color: "var(--primaryText)", border: "1px solid var(--primaryBorder)", background: "var(--surface)" }}
        onClick={onOpenRules}
      >
        Ver las 7 reglas
      </span>
    </div>
  );
}

function FilterBuilder({ fields, onAdd }) {
  const [field, setField] = useState(fields[0] || "");
  const [op, setOp] = useState("es");
  const [value, setValue] = useState("");
  const isNum = NUMERIC_FIELDS.has(field);

  useEffect(() => { setOp(isNum ? "eq" : "es"); setValue(""); }, [field]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-[14px]">
      <div style={{ fontWeight: 700, fontSize: "12px", marginBottom: "11px" }}>Nuevo filtro</div>
      <div className="flex gap-2 items-center">
        <select
          value={field}
          onChange={(e) => setField(e.target.value)}
          className="flex-1 h-[33px] rounded-lg px-2 border outline-none cursor-pointer"
          style={{ background: "var(--surface)", borderColor: "var(--border)", fontFamily: "'JetBrains Mono', monospace", fontSize: "11.5px", fontWeight: 600, color: "var(--fg)" }}
        >
          {fields.map((f) => <option key={f} value={f}>{FIELD_LABELS[f] || f}</option>)}
        </select>
        <select
          value={op}
          onChange={(e) => setOp(e.target.value)}
          className="flex-none w-[110px] h-[33px] rounded-lg px-2 border outline-none cursor-pointer"
          style={{ background: "var(--surface)", borderColor: "var(--border)", fontSize: "11.5px", fontWeight: 600, color: "var(--fg)" }}
        >
          {(isNum ? NUM_OPS : TEXT_OPS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <div className="mt-2">
        <input
          type={isNum ? "number" : "text"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={isNum ? "Valor numérico…" : "Valor…"}
          className="w-full h-[33px] rounded-lg px-[10px] border outline-none"
          style={{ background: "var(--surface)", borderColor: "var(--border)", fontFamily: "'JetBrains Mono', monospace", fontSize: "11.5px", fontWeight: 600, color: "var(--fg)" }}
        />
      </div>
      <div className="flex justify-end mt-3">
        <button
          disabled={value === ""}
          onClick={() => onAdd({ field, op, value })}
          className="h-[31px] px-[14px] rounded-lg disabled:opacity-40"
          style={{ background: "var(--primary)", color: "#fff", fontWeight: 700, fontSize: "11.5px", border: "none" }}
        >
          Agregar filtro
        </button>
      </div>
    </div>
  );
}

function ColumnsSelector({ allCols, visibleCols, onChange }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-[9px]">
        <span style={{ fontWeight: 700, fontSize: "11px" }}>Mostrar columnas</span>
        <span className="cursor-pointer" style={{ fontWeight: 600, fontSize: "10px", color: "var(--primaryText)" }} onClick={() => onChange(null)}>Todas</span>
      </div>
      <div className="flex flex-col gap-[1px] max-h-[290px] overflow-auto">
        {allCols.map((c) => {
          const on = !visibleCols || visibleCols.has(c.key);
          return (
            <div
              key={c.key}
              onClick={() => {
                const next = new Set(visibleCols || allCols.map((x) => x.key));
                if (next.has(c.key)) next.delete(c.key); else next.add(c.key);
                onChange(next);
              }}
              className="flex items-center gap-[9px] px-[6px] py-[5px] rounded-md cursor-pointer"
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--rowHover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span
                className="w-[17px] h-[17px] rounded-[4px] flex items-center justify-center flex-none"
                style={{ border: `1.5px solid ${on ? "var(--primary)" : "var(--border2)"}`, background: on ? "var(--primary)" : "transparent" }}
              >
                {on && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>}
              </span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: "11px" }}>{c.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
