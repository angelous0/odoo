import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import TablesRail from "@/explorer/TablesRail";
import TablePanel from "@/explorer/TablePanel";

const GROUP_ORDER = ["Favoritos", "Ventas", "Stock", "Productos", "Contactos", "Sistema"];

export default function ExplorerMode({ globalSearch, selTable, setSelTable }) {
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const loadTables = () => {
    setLoading(true);
    Promise.all([api.get("/schema/tables-fast"), api.get("/schema/relations"), api.get("/sync-jobs")])
      .then(([tRes, rRes, sRes]) => {
        const relTables = rRes.data.tables || {};
        const jobs = sRes.data.jobs || [];
        const lastSync = jobs.reduce((max, j) => {
          if (!j.last_success_at) return max;
          const t = new Date(j.last_success_at).getTime();
          return t > max ? t : max;
        }, 0);
        const merged = (tRes.data.tables || []).map((t) => {
          const meta = relTables[t.name] || {};
          return {
            ...t,
            group: meta.group || "Sistema",
            label: meta.label || t.name,
            favorite: !!meta.favorite,
            from: meta.from || [],
            refs: meta.refs || [],
            ref_by: meta.ref_by || [],
            last_sync_at: lastSync ? new Date(lastSync).toISOString() : null,
          };
        });
        setTables(merged);
      })
      .catch(() => setTables([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTables();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grouped = useMemo(() => {
    const q = globalSearch.trim().toLowerCase();
    const filtered = q
      ? tables.filter((t) => t.name.toLowerCase().includes(q) || t.label.toLowerCase().includes(q))
      : tables;
    const favs = filtered.filter((t) => t.favorite);
    const groups = GROUP_ORDER.map((g) => ({
      group: g,
      items: g === "Favoritos" ? favs : filtered.filter((t) => t.group === g),
    })).filter((g) => g.items.length > 0);
    return groups;
  }, [tables, globalSearch]);

  const selected = tables.find((t) => t.name === selTable) || tables[0];

  const syncAll = async () => {
    setSyncing(true);
    try {
      await api.post("/sync/run", { target: "ALL" });
    } catch (e) {}
    loadTables();
    setSyncing(false);
  };

  const errorCount = tables.filter((t) => !t.exists).length;

  return (
    <>
      <TablesRail
        grouped={grouped}
        selTable={selTable}
        onSelect={setSelTable}
        totalCount={tables.length}
        errorCount={errorCount}
        syncing={syncing}
        onSyncAll={syncAll}
        loading={loading}
      />
      <TablePanel
        table={selected}
        onNavigate={setSelTable}
        onRefreshMeta={loadTables}
      />
    </>
  );
}
