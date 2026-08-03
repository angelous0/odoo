import { useEffect, useState } from "react";
import "@/index.css";
import { Toaster } from "sonner";
import { Database, Search, Sun, Moon, Bell } from "lucide-react";
import { getInitialTheme, applyTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { GotoTableContext } from "@/lib/nav";
import ExplorerMode from "@/explorer/ExplorerMode";
import ConnectionsMode from "@/connections/ConnectionsMode";

export default function App() {
  const [mode, setMode] = useState("data");
  const [theme, setTheme] = useState(getInitialTheme);
  const [globalSearch, setGlobalSearch] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [syncJobs, setSyncJobs] = useState([]);
  const [selTable, setSelTable] = useState("v_pos_line_real");

  const gotoTable = (table) => {
    setSelTable(table);
    setMode("data");
  };

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    api
      .get("/sync-jobs")
      .then((res) => setSyncJobs(res.data.jobs || []))
      .catch(() => setSyncJobs([]));
  }, []);

  const failingJobs = syncJobs.filter((j) => j.last_error);

  return (
    <div
      className="fixed inset-0 flex flex-col overflow-hidden"
      style={{ background: "var(--surface)", color: "var(--fg)", fontFamily: "'Manrope', system-ui, sans-serif" }}
    >
      <Toaster theme={theme} position="top-right" richColors />

      {/* TOP BAR */}
      <div
        className="flex-none h-[54px] flex items-center justify-between px-4 border-b z-30"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Database size={19} style={{ color: "var(--primary)" }} strokeWidth={1.8} />
            <span
              style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "15px", letterSpacing: "-.02em" }}
            >
              odoo<span style={{ color: "var(--primary)" }}>·</span>ODS
            </span>
          </div>
          <div className="flex gap-[2px] p-[3px] rounded-lg border" style={{ background: "var(--card2)", borderColor: "var(--border)" }}>
            {[
              { key: "data", label: "Explorador" },
              { key: "conn", label: "Conexiones" },
            ].map((m) => (
              <span
                key={m.key}
                onClick={() => setMode(m.key)}
                className="inline-flex items-center h-[27px] px-3 rounded-md cursor-pointer select-none"
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  background: mode === m.key ? "var(--surface)" : "transparent",
                  color: mode === m.key ? "var(--fg)" : "var(--muted)",
                  boxShadow: mode === m.key ? "0 1px 2px rgba(0,0,0,.1)" : "none",
                }}
              >
                {m.label}
              </span>
            ))}
          </div>
        </div>

        <div className="flex-1 max-w-[440px] mx-[18px] relative">
          <Search size={15} className="absolute left-[11px] top-1/2 -translate-y-1/2" style={{ color: "var(--muted2)" }} />
          <input
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            placeholder="Buscar en todas las tablas y columnas…"
            className="w-full h-[35px] rounded-[9px] pl-[33px] pr-3 outline-none border"
            style={{ background: "var(--card2)", borderColor: "var(--border)", color: "var(--fg)", fontSize: "12.5px", fontWeight: 500 }}
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            title="Cambiar tema claro / oscuro"
            onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
            className="w-[35px] h-[35px] flex items-center justify-center rounded-[9px] border"
            style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--fg)" }}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <div className="relative">
            <button
              title="Registro de cargas"
              onClick={() => setNotifOpen((o) => !o)}
              className="relative w-[35px] h-[35px] flex items-center justify-center rounded-[9px] border"
              style={{ borderColor: "var(--border)", background: "var(--card2)", color: "var(--fg)" }}
            >
              <Bell size={16} />
              {failingJobs.length > 0 && (
                <span
                  className="absolute -top-1 -right-1 min-w-[16px] h-4 px-[3px] rounded-full flex items-center justify-center text-white"
                  style={{ background: "var(--danger)", fontFamily: "'JetBrains Mono', monospace", fontSize: "9px", fontWeight: 700 }}
                >
                  {failingJobs.length}
                </span>
              )}
            </button>
            {notifOpen && (
              <div
                className="absolute top-[42px] right-0 w-[358px] rounded-[13px] border overflow-hidden z-[80]"
                style={{ background: "var(--card)", borderColor: "var(--border)", boxShadow: "var(--shadow)" }}
              >
                <div
                  className="px-4 py-[11px] border-b flex items-center justify-between"
                  style={{ borderColor: "var(--border)" }}
                >
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "12.5px" }}>
                    Registro de cargas
                  </span>
                  <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)" }}>
                    {failingJobs.length} avisos
                  </span>
                </div>
                {failingJobs.length === 0 ? (
                  <div className="px-4 py-4 text-center" style={{ fontSize: "11.5px", color: "var(--muted2)" }}>
                    Sin errores recientes.
                  </div>
                ) : (
                  failingJobs.map((j) => (
                    <div key={j.job_code} className="px-4 py-[11px] border-b flex gap-3" style={{ borderColor: "var(--border)" }}>
                      <span
                        className="w-[7px] h-[7px] rounded-full mt-1 flex-none"
                        style={{ background: "var(--danger)" }}
                      />
                      <div className="flex-1 min-w-0">
                        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: "11px" }}>
                          {j.job_code}
                        </div>
                        <div className="mt-[3px]" style={{ fontSize: "11px", color: "var(--muted)", lineHeight: 1.45 }}>
                          {j.last_error}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BODY */}
      <GotoTableContext.Provider value={gotoTable}>
        <div className="flex-1 flex min-h-0">
          {mode === "data" ? (
            <ExplorerMode globalSearch={globalSearch} selTable={selTable} setSelTable={setSelTable} />
          ) : (
            <ConnectionsMode globalSearch={globalSearch} />
          )}
        </div>
      </GotoTableContext.Provider>
    </div>
  );
}
