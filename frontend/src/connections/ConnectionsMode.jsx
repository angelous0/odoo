import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { ago, abs, fmt } from "@/lib/format";
import DataGrid from "@/components/DataGrid";
import { useGotoTable } from "@/lib/nav";

function extractTable(query) {
  const m = /odoo\.([a-zA-Z_][a-zA-Z0-9_]*)/.exec(query || "");
  return m ? m[1] : null;
}
function extractAction(query) {
  const w = (query || "").trim().split(/\s+/)[0]?.toUpperCase();
  return ["SELECT", "INSERT", "UPDATE", "DELETE"].includes(w) ? w : w || "OTHER";
}
function actionBadge(a) {
  if (a === "SELECT") return "emerald";
  if (a === "INSERT" || a === "UPDATE") return "amber";
  if (a === "DELETE") return "danger";
  return "neutral";
}

export default function ConnectionsMode({ globalSearch }) {
  const gotoTable = useGotoTable();
  const [consumers, setConsumers] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selCons, setSelCons] = useState("resumen");
  const [connTab, setConnTab] = useState("extrae");

  const load = () => {
    setLoading(true);
    Promise.all([api.get("/monitoring/consumers"), api.get("/monitoring/activity", { params: { limit: 200 } })])
      .then(([cRes, aRes]) => {
        setConsumers(cRes.data.consumers || []);
        setActivity(aRes.data.activity || []);
      })
      .catch(() => { setConsumers([]); setActivity([]); })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  const q = globalSearch.trim().toLowerCase();
  const filteredConsumers = q ? consumers.filter((c) => c.consumer.toLowerCase().includes(q)) : consumers;

  const activeCount = consumers.filter((c) => c.has_active).length;
  const totalQ = activity.length;

  const consumerActivity = (name) => activity.filter((a) => a.consumer === name);

  const buildActivityGrid = (list) => {
    const cols = [
      { key: "hora", label: "Hora", align: "left", width: 96 },
      { key: "consumer", label: "Consumidor", align: "left", width: 156 },
      { key: "accion", label: "Acción", align: "left", width: 96 },
      { key: "tabla", label: "Tabla / vista", align: "left", width: "flex" },
      { key: "estado", label: "Estado", align: "left", width: 90 },
    ];
    const rows = list.map((a, i) => {
      const action = extractAction(a.query);
      const tbl = extractTable(a.query) || "—";
      return {
        key: a.pid + "-" + i,
        onClick: tbl !== "—" ? () => gotoTable(tbl) : undefined,
        cells: [
          { value: abs(a.query_start), tone: "muted" },
          { value: a.consumer },
          { value: action, badge: actionBadge(action) },
          { value: tbl, tone: "primary" },
          { value: a.state, tone: a.state === "active" ? "primary" : "muted" },
        ],
      };
    });
    return { cols, rows };
  };

  const buildConsumersGrid = () => {
    const cols = [
      { key: "consumer", label: "Consumidor", align: "left", width: "flex" },
      { key: "tipo", label: "Tipo", align: "left", width: 132 },
      { key: "estado", label: "Estado", align: "left", width: 108 },
      { key: "host", label: "Host / origen", align: "left", width: 200 },
      { key: "ultimo", label: "Último acceso", align: "left", width: 118 },
      { key: "queries", label: "Conexiones", align: "right", width: 92 },
      { key: "lee", label: "Lee", align: "right", width: 78 },
    ];
    const rows = filteredConsumers.map((c) => {
      const acts = consumerActivity(c.consumer);
      const tables = new Set(acts.map(extractTable).filter(Boolean));
      return {
        key: c.consumer + c.client_addr,
        onClick: () => setSelCons(c.consumer),
        cells: [
          { value: c.consumer, strong: true },
          { value: c.client_addr ? "SQL / red" : "SQL local", tone: "muted" },
          { value: c.has_active ? "Activo" : "Conectado", badge: c.has_active ? "emerald" : "neutral" },
          { value: c.client_addr || "local", tone: "muted" },
          { value: `hace ${ago(c.last_query_at)}`, tone: "muted" },
          { value: fmt(c.connections) },
          { value: tables.size, tone: "muted" },
        ],
      };
    });
    return { cols, rows };
  };

  const cons = consumers.find((c) => c.consumer === selCons);
  const consActs = useMemo(() => (cons ? activity.filter((a) => a.consumer === cons.consumer) : []), [cons, activity]);
  const consTables = useMemo(() => {
    const map = new Map();
    consActs.forEach((a) => {
      const t = extractTable(a.query);
      if (!t) return;
      const existing = map.get(t) || { table: t, count: 0, lastAt: a.query_start };
      existing.count += 1;
      if (new Date(a.query_start) > new Date(existing.lastAt)) existing.lastAt = a.query_start;
      map.set(t, existing);
    });
    return Array.from(map.values());
  }, [consActs]);

  const readsGrid = {
    cols: [
      { key: "table", label: "Tabla / vista", align: "left", width: 220 },
      { key: "count", label: "Consultas", align: "right", width: 110 },
      { key: "last", label: "Última lectura", align: "left", width: "flex" },
    ],
    rows: consTables.map((t) => ({
      key: t.table,
      onClick: () => gotoTable(t.table),
      cells: [
        { value: t.table, tone: "primary" },
        { value: fmt(t.count) },
        { value: `hace ${ago(t.lastAt)}`, tone: "muted" },
      ],
    })),
  };

  return (
    <>
      {/* RAIL */}
      <div className="flex-none w-[260px] border-r flex flex-col min-h-0" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
        <div className="p-3 pb-2">
          <div className="relative">
            <Search size={14} className="absolute left-[10px] top-1/2 -translate-y-1/2" style={{ color: "var(--muted2)" }} />
            <input
              placeholder="Filtrar consumidores…"
              className="w-full h-[31px] rounded-lg pl-[31px] pr-2 outline-none border"
              style={{ background: "var(--surface)", borderColor: "var(--border)", fontSize: "11.5px", fontWeight: 500, color: "var(--fg)" }}
              readOnly
            />
          </div>
        </div>
        <div className="flex-1 overflow-auto pb-2">
          <div className="px-4 pt-[11px] pb-1">
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".09em", textTransform: "uppercase", color: "var(--muted2)" }}>
              Monitoreo
            </span>
          </div>
          {[{ consumer: "resumen", label: "Resumen" }, ...filteredConsumers.map((c) => ({ consumer: c.consumer, label: c.consumer, dotOk: c.has_active }))].map((c) => {
            const on = selCons === c.consumer;
            return (
              <div
                key={c.consumer}
                onClick={() => setSelCons(c.consumer)}
                className="flex items-center gap-2 mx-[7px] my-[1px] px-[9px] py-[6px] rounded-[7px] cursor-pointer"
                style={{ borderLeft: on ? "2px solid var(--primary)" : "2px solid transparent", background: on ? "var(--sel)" : "transparent" }}
              >
                <span className="w-[7px] h-[7px] rounded-full flex-none" style={{ background: c.consumer === "resumen" || c.dotOk ? "var(--primary)" : "var(--warn)" }} />
                <span className="flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap" style={{ fontSize: "11.5px", fontWeight: 600 }}>{c.label}</span>
              </div>
            );
          })}
        </div>
        <div className="flex-none border-t px-[14px] py-[10px]" style={{ borderColor: "var(--border)" }}>
          <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)" }}>
            <span style={{ color: "var(--primary)" }}>{activeCount} activos</span> · {consumers.length} consumidores
          </span>
        </div>
      </div>

      {/* MAIN */}
      <div className="flex-1 flex flex-col min-w-0" style={{ background: "var(--surface)" }}>
        {loading ? (
          <div className="flex-1 flex items-center justify-center" style={{ color: "var(--muted2)" }}>Cargando…</div>
        ) : selCons === "resumen" ? (
          <>
            <div className="flex-none px-6 py-4 border-b" style={{ borderColor: "var(--border)" }}>
              <h2 style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "19px", letterSpacing: "-.01em" }}>
                Quién se conecta al schema odoo
              </h2>
              <p className="mt-[6px]" style={{ fontSize: "12px", color: "var(--muted)" }}>
                Apps y procesos que leen los datos (pg_stat_activity) ·{" "}
                <span style={{ color: "var(--primary)", fontWeight: 700 }}>{activeCount} activos</span> ·{" "}
                <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)" }}>{totalQ}</span> conexiones vistas
              </p>
            </div>
            <div className="flex-1 overflow-auto px-6 py-4">
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)", marginBottom: 9 }}>
                Consumidores
              </div>
              <DataGrid {...buildConsumersGrid()} minWidth={900} />
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "9.5px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--muted2)", margin: "22px 0 9px" }}>
                Actividad reciente
              </div>
              <DataGrid {...buildActivityGrid(activity)} minWidth={860} />
            </div>
          </>
        ) : cons ? (
          <>
            <div className="flex-none px-6 pt-[15px] border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex items-center gap-[10px] flex-wrap">
                <h2 style={{ fontWeight: 700, fontSize: "18px", letterSpacing: "-.01em" }}>{cons.consumer}</h2>
                <span className="px-2 py-[2px] rounded-md border" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "11px", fontWeight: 600, background: "var(--card2)", borderColor: "var(--border)", color: "var(--muted)" }}>
                  {cons.client_addr ? "SQL / red" : "SQL local"}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-[7px] flex-wrap" style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{cons.client_addr || "local"}</span>
                <span style={{ color: "var(--border2)" }}>·</span>
                <span>última conexión</span><span style={{ color: "var(--primary)", fontWeight: 700 }}>hace {ago(cons.last_query_at)}</span>
                <span style={{ color: "var(--border2)" }}>·</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)", fontWeight: 600 }}>{fmt(cons.connections)}</span><span>conexiones</span>
              </div>
              <div className="flex gap-[3px] mt-[14px]">
                {[["extrae", "Qué extrae"], ["actividad", "Actividad"]].map(([k, l]) => (
                  <button
                    key={k}
                    onClick={() => setConnTab(k)}
                    className="px-[15px] py-[9px] rounded-t-lg"
                    style={{ border: "none", borderBottom: connTab === k ? "2px solid var(--primary)" : "2px solid transparent", fontSize: "12.5px", fontWeight: connTab === k ? 700 : 600, background: "transparent", color: connTab === k ? "var(--fg)" : "var(--muted)" }}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>
            {connTab === "extrae" ? (
              <div className="flex-1 overflow-auto px-6 py-4">
                <p className="mb-[11px]" style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                  Tablas y vistas que <span style={{ fontWeight: 700, color: "var(--fg)" }}>{cons.consumer}</span> consultó recientemente · clic en una fila para abrir la tabla
                </p>
                <DataGrid {...readsGrid} minWidth={560} emptyLabel="Sin consultas identificables aún." />
              </div>
            ) : (
              <div className="flex-1 overflow-auto px-6 py-4">
                <p className="mb-[11px]" style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                  Últimas consultas de <span style={{ fontWeight: 700, color: "var(--fg)" }}>{cons.consumer}</span>
                </p>
                <DataGrid {...buildActivityGrid(consActs)} minWidth={860} />
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center" style={{ color: "var(--muted2)" }}>Consumidor no encontrado.</div>
        )}
      </div>
    </>
  );
}
