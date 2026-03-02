import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  RefreshCw, Play, Users, ShoppingCart, Package, Warehouse,
  CreditCard, Clock, CheckCircle, XCircle, Loader2, Zap,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fmtDate = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return d.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "2-digit" }) +
    " " + d.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
};

const MACROS = [
  {
    id: "clientes",
    label: "Actualizar Clientes",
    icon: Users,
    jobs: ["RES_PARTNER"],
    color: "text-blue-400",
    bg: "hover:bg-blue-950/40",
  },
  {
    id: "ventas",
    label: "Actualizar Ventas",
    icon: ShoppingCart,
    jobs: ["POS_ORDERS"],
    color: "text-amber-400",
    bg: "hover:bg-amber-950/40",
  },
  {
    id: "productos",
    label: "Actualizar Productos",
    icon: Package,
    jobs: ["PRODUCTS", "ATTRIBUTES"],
    color: "text-emerald-400",
    bg: "hover:bg-emerald-950/40",
  },
  {
    id: "stock",
    label: "Actualizar Stock",
    icon: Warehouse,
    jobs: ["STOCK_QUANTS"],
    color: "text-purple-400",
    bg: "hover:bg-purple-950/40",
  },
  {
    id: "creditos",
    label: "Actualizar Créditos",
    icon: CreditCard,
    jobs: ["AR_CREDIT_INVOICES"],
    color: "text-rose-400",
    bg: "hover:bg-rose-950/40",
  },
];

function StatusBadge({ job, lastRun, runningJobs }) {
  const isRunning = runningJobs.includes(job.job_code) || lastRun?.status === "RUNNING";
  if (isRunning) {
    return <Badge className="bg-blue-600/20 text-blue-400 border-blue-600/40 font-mono text-xs" data-testid={`badge-running-${job.job_code}`}><Loader2 className="h-3 w-3 mr-1 animate-spin" />RUNNING</Badge>;
  }
  if (job.last_error) {
    return <Badge variant="destructive" className="font-mono text-xs" data-testid={`badge-error-${job.job_code}`}><XCircle className="h-3 w-3 mr-1" />ERROR</Badge>;
  }
  if (job.last_success_at) {
    return <Badge className="bg-emerald-600/20 text-emerald-400 border-emerald-600/40 font-mono text-xs" data-testid={`badge-ok-${job.job_code}`}><CheckCircle className="h-3 w-3 mr-1" />OK</Badge>;
  }
  return <Badge variant="outline" className="font-mono text-xs text-muted-foreground">—</Badge>;
}

export default function SyncControlPage() {
  const [jobs, setJobs] = useState([]);
  const [lastRuns, setLastRuns] = useState({});
  const [runningJobs, setRunningJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningMacros, setRunningMacros] = useState({});
  const pollingRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/odoo-sync/job-status`);
      setJobs(res.data.jobs || []);
      setLastRuns(res.data.last_runs || {});
      setRunningJobs(res.data.running_jobs || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Polling when something is running
  useEffect(() => {
    const hasRunning = runningJobs.length > 0 || Object.values(runningMacros).some(Boolean);
    if (hasRunning) {
      pollingRef.current = setInterval(fetchStatus, 3000);
    } else {
      clearInterval(pollingRef.current);
    }
    return () => clearInterval(pollingRef.current);
  }, [runningJobs, runningMacros, fetchStatus]);

  const handleRunJob = async (jobCode) => {
    try {
      const res = await axios.post(`${API}/odoo-sync/run`, { job_code: jobCode });
      if (res.data.success) {
        toast.info(`Job ${jobCode} iniciado`);
        setRunningJobs((prev) => [...prev, jobCode]);
        // Start polling
        const poll = setInterval(async () => {
          const st = await axios.get(`${API}/odoo-sync/job-status`, { params: { job_code: jobCode } });
          const lr = st.data.last_run;
          if (lr && lr.status !== "RUNNING") {
            clearInterval(poll);
            setRunningJobs((prev) => prev.filter((j) => j !== jobCode));
            if (lr.status === "OK") {
              toast.success(`${jobCode}: ${lr.rows_upserted || 0} filas sincronizadas`);
            } else {
              toast.error(`${jobCode}: ${lr.error_message || "Error"}`);
            }
            fetchStatus();
          }
        }, 3000);
      } else {
        toast.warning(res.data.message);
      }
    } catch (e) {
      toast.error(`Error: ${e.message}`);
    }
  };

  const handleRunMacro = async (macro) => {
    setRunningMacros((prev) => ({ ...prev, [macro.id]: true }));
    try {
      const res = await axios.post(`${API}/odoo-sync/run-batch`, {
        job_codes: macro.jobs,
        stop_on_error: true,
      });
      if (res.data.success) {
        toast.info(`${macro.label}: ${macro.jobs.length} jobs iniciados`);
        setRunningJobs((prev) => [...prev, ...macro.jobs]);
        // Poll until all jobs complete
        const poll = setInterval(async () => {
          const st = await axios.get(`${API}/odoo-sync/job-status`);
          const running = st.data.running_jobs || [];
          const stillRunning = macro.jobs.some((j) => running.includes(j));
          setRunningJobs(running);
          setJobs(st.data.jobs || []);
          setLastRuns(st.data.last_runs || {});
          if (!stillRunning) {
            clearInterval(poll);
            setRunningMacros((prev) => ({ ...prev, [macro.id]: false }));
            const results = macro.jobs.map((jc) => {
              const lr = st.data.last_runs?.[jc];
              return `${jc}: ${lr?.status === "OK" ? (lr.rows_upserted || 0) + " filas" : lr?.error_message || "?"}`;
            });
            toast.success(`${macro.label} completado`, { description: results.join(" | ") });
          }
        }, 3000);
      } else {
        toast.warning(res.data.message);
        setRunningMacros((prev) => ({ ...prev, [macro.id]: false }));
      }
    } catch (e) {
      toast.error(`Error: ${e.message}`);
      setRunningMacros((prev) => ({ ...prev, [macro.id]: false }));
    }
  };

  const isJobBusy = (jobCode) => runningJobs.includes(jobCode);
  const isMacroBusy = (macro) => runningMacros[macro.id] || macro.jobs.some((j) => isJobBusy(j));

  const getMacroLastUpdate = (macro) => {
    const dates = macro.jobs
      .map((jc) => jobs.find((j) => j.job_code === jc)?.last_success_at)
      .filter(Boolean)
      .map((d) => new Date(d).getTime());
    if (dates.length === 0) return null;
    return new Date(Math.max(...dates)).toISOString();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="sync-control-title">
            Sync Control
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Control manual de sincronización Odoo &rarr; ODS
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchStatus} data-testid="refresh-sync-control">
          <RefreshCw className="h-4 w-4 mr-2" />Refrescar
        </Button>
      </div>

      {/* Quick Macro Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="macro-buttons">
        {MACROS.map((macro) => {
          const busy = isMacroBusy(macro);
          const lastUpdate = getMacroLastUpdate(macro);
          const Icon = macro.icon;
          return (
            <Card key={macro.id} className={`border-border bg-card transition-colors ${macro.bg}`}>
              <CardContent className="p-4 flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Icon className={`h-5 w-5 ${macro.color}`} />
                  <span className="text-sm font-medium">{macro.label}</span>
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  {lastUpdate ? (
                    <span><Clock className="h-3 w-3 inline mr-1" />{fmtDate(lastUpdate)}</span>
                  ) : "Sin ejecutar"}
                </div>
                <Button
                  size="sm"
                  variant={busy ? "outline" : "default"}
                  disabled={busy}
                  onClick={() => handleRunMacro(macro)}
                  className="w-full"
                  data-testid={`macro-btn-${macro.id}`}
                >
                  {busy ? (
                    <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" />Sincronizando...</>
                  ) : (
                    <><Zap className="h-4 w-4 mr-1.5" />Ejecutar</>
                  )}
                </Button>
                <div className="text-xs text-muted-foreground font-mono">
                  Jobs: {macro.jobs.join(", ")}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Job Monitor Table */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <RefreshCw className="h-4 w-4 text-primary" /> Monitor de Jobs
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12"><RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" /></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-xs">job_code</TableHead>
                  <TableHead className="font-mono text-xs text-center">Estado</TableHead>
                  <TableHead className="font-mono text-xs">mode</TableHead>
                  <TableHead className="font-mono text-xs">schedule</TableHead>
                  <TableHead className="font-mono text-xs text-right">chunk</TableHead>
                  <TableHead className="font-mono text-xs">scope</TableHead>
                  <TableHead className="font-mono text-xs">Última OK</TableHead>
                  <TableHead className="font-mono text-xs">Último run</TableHead>
                  <TableHead className="font-mono text-xs text-right">Filas</TableHead>
                  <TableHead className="font-mono text-xs">Error</TableHead>
                  <TableHead className="font-mono text-xs text-center">Acción</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => {
                  const lr = lastRuns[job.job_code];
                  const busy = isJobBusy(job.job_code);
                  return (
                    <TableRow key={job.job_code} data-testid={`job-row-${job.job_code}`}>
                      <TableCell className="font-mono text-sm font-medium text-primary">{job.job_code}</TableCell>
                      <TableCell className="text-center">
                        <StatusBadge job={job} lastRun={lr} runningJobs={runningJobs} />
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{job.mode}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{job.schedule_type}</TableCell>
                      <TableCell className="font-mono text-xs text-right">{job.chunk_size}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{job.company_scope}</TableCell>
                      <TableCell className="font-mono text-xs">{fmtDate(job.last_success_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{fmtDate(lr?.started_at)}</TableCell>
                      <TableCell className="font-mono text-xs text-right">{lr?.rows_upserted ?? "—"}</TableCell>
                      <TableCell className="text-xs text-destructive max-w-[150px] truncate" title={job.last_error || ""}>
                        {job.last_error ? job.last_error.substring(0, 40) + "..." : "—"}
                      </TableCell>
                      <TableCell className="text-center">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => handleRunJob(job.job_code)}
                          className="h-7 px-2"
                          data-testid={`run-btn-${job.job_code}`}
                        >
                          {busy ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <><Play className="h-3.5 w-3.5 mr-1" />Run</>
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
