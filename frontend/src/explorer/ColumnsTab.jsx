import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import DataGrid from "@/components/DataGrid";

export default function ColumnsTab({ table }) {
  const [columns, setColumns] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get("/schema/table-columns", { params: { table: table.name } })
      .then((res) => setColumns(res.data.columns || []))
      .catch(() => setColumns([]))
      .finally(() => setLoading(false));
  }, [table.name]);

  const cols = [
    { key: "name", label: "Columna", align: "left", width: "flex" },
    { key: "type", label: "Tipo", align: "left", width: 160 },
    { key: "key", label: "Clave", align: "left", width: 80 },
    { key: "origin", label: "Origen", align: "left", width: "flex" },
  ];

  const rows = (columns || []).map((c) => ({
    key: c.name,
    cells: [
      { value: c.name, strong: true },
      { value: c.type, tone: "muted" },
      c.key === "PK" ? { value: "PK", badge: "emerald" } : c.key === "FK" ? { value: "FK", badge: "amber" } : { value: "—", tone: "muted" },
      { value: c.origin || "—", tone: "muted" },
    ],
  }));

  return (
    <div className="flex-1 overflow-auto px-6 py-4">
      {loading ? (
        <div className="text-center py-10" style={{ color: "var(--muted2)" }}>Cargando…</div>
      ) : columns && columns.length > 0 ? (
        <>
          <p className="mb-[11px]" style={{ fontSize: "11.5px", color: "var(--muted)" }}>
            Estructura de <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "var(--fg)", fontWeight: 600 }}>{table.name}</span>{" "}
            · {columns.length} columnas · <span style={{ color: "var(--primaryText)" }}>PK</span>/<span style={{ color: "var(--warn)" }}>FK</span> y tabla de origen
          </p>
          <DataGrid cols={cols} rows={rows} minWidth={640} />
        </>
      ) : (
        <div className="text-center py-16" style={{ color: "var(--muted2)", fontSize: "12.5px" }}>
          No se pudo leer el esquema de <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{table.name}</span>.
        </div>
      )}
    </div>
  );
}
