import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RefreshCw, Activity, CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function LogsPage({ api }) {
  const [logs, setLogs] = useState([]);
  const [filterStatus, setFilterStatus] = useState("ALL");
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/sync-logs`);
      setLogs(res.data.logs || []);
    } catch (e) {
      console.error("Error fetching logs:", e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Auto-refresh every 5s if there are RUNNING jobs
  useEffect(() => {
    const hasRunning = logs.some((l) => l.status === "RUNNING");
    if (!hasRunning) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [logs, fetchLogs]);

  const filteredLogs =
    filterStatus === "ALL"
      ? logs
      : logs.filter((l) => l.status === filterStatus);

  const formatDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1
            className="text-3xl md:text-4xl font-bold tracking-tight"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
            data-testid="logs-title"
          >
            Historial de Ejecución
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Registro de ejecuciones de sincronización &mdash;{" "}
            <code className="text-primary font-mono">odoo.sync_run_log</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={filterStatus}
            onValueChange={setFilterStatus}
            data-testid="filter-status"
          >
            <SelectTrigger className="w-[140px] h-9 text-sm" data-testid="filter-status-trigger">
              <SelectValue placeholder="Filtrar estado" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Todos</SelectItem>
              <SelectItem value="OK">OK</SelectItem>
              <SelectItem value="RUNNING">En Proceso</SelectItem>
              <SelectItem value="ERROR">ERROR</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchLogs}
            data-testid="refresh-logs-btn"
            aria-label="Refrescar historial"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refrescar
          </Button>
        </div>
      </div>

      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle
            className="text-base font-medium flex items-center gap-2"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <Activity className="h-4 w-4 text-primary" />
            Ejecuciones Recientes ({filteredLogs.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Cargando...</span>
            </div>
          ) : filteredLogs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-xs">ID</TableHead>
                  <TableHead className="font-mono text-xs">Job Code</TableHead>
                  <TableHead className="font-mono text-xs">Empresa</TableHead>
                  <TableHead className="font-mono text-xs">Inicio</TableHead>
                  <TableHead className="font-mono text-xs">Fin</TableHead>
                  <TableHead className="font-mono text-xs text-center">Estado</TableHead>
                  <TableHead className="font-mono text-xs text-right">Upserted</TableHead>
                  <TableHead className="font-mono text-xs text-right">Updated</TableHead>
                  <TableHead className="font-mono text-xs">Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.map((log) => (
                  <TableRow key={log.id} data-testid={`log-row-${log.id}`}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.id}
                    </TableCell>
                    <TableCell className="font-mono text-sm font-medium text-primary">
                      {log.job_code}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {log.company_key}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {formatDate(log.started_at)}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.ended_at ? formatDate(log.ended_at) : log.status === "RUNNING" ? (
                        <span className="text-yellow-400 animate-pulse">sincronizando...</span>
                      ) : "—"}
                    </TableCell>
                    <TableCell className="text-center">
                      {log.status === "OK" ? (
                        <Badge className="bg-primary/20 text-primary border-primary/30 text-[10px] font-mono">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          OK
                        </Badge>
                      ) : log.status === "RUNNING" ? (
                        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 text-[10px] font-mono animate-pulse">
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          EN PROCESO
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px] font-mono">
                          <XCircle className="h-3 w-3 mr-1" />
                          ERROR
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {log.rows_upserted}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {log.rows_updated}
                    </TableCell>
                    <TableCell className="text-sm max-w-[250px] truncate">
                      {log.error_message ? (
                        <span className="text-destructive text-xs">
                          {log.error_message}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <Activity className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                No hay registros de ejecución.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Los registros aparecerán cuando se ejecuten sincronizaciones.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
