import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  RefreshCw, HeartPulse, Database, AlertTriangle, CheckCircle, XCircle,
} from "lucide-react";

const fmtDate = (iso) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

export default function HealthPage({ api }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/health`);
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const orphanOk = data?.orphan_lines === 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="health-title">
            Health
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Conteos, integridad y errores recientes
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} data-testid="refresh-health-btn">
          <RefreshCw className="h-4 w-4 mr-2" />Refrescar
        </Button>
      </div>

      {/* Table Counts */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <Database className="h-4 w-4 text-primary" /> Conteos por Tabla
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {(data?.tables || []).map((t) => (
              <div key={t.table} className="flex items-center justify-between p-4 rounded-lg bg-secondary/50 border border-border" data-testid={`health-card-${t.table}`}>
                <div>
                  <p className="font-mono text-xs text-muted-foreground">odoo.{t.table}</p>
                  <p className="text-2xl font-bold font-mono tracking-tight mt-1">{t.count.toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Último write</p>
                  <p className="font-mono text-xs mt-1">{fmtDate(t.max_write_date)}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* POS by Company */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <HeartPulse className="h-4 w-4 text-primary" /> POS por Empresa
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="font-mono text-xs">company_key</TableHead>
                <TableHead className="font-mono text-xs text-right">Orders</TableHead>
                <TableHead className="font-mono text-xs">Último write_date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.pos_by_company || []).map((p) => (
                <TableRow key={p.company_key} data-testid={`health-pos-${p.company_key}`}>
                  <TableCell className="font-mono text-sm font-medium text-primary">{p.company_key}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{p.count.toLocaleString()}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{fmtDate(p.max_write_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Integrity */}
      <Card className={`border-border ${orphanOk ? "bg-card" : "bg-destructive/5 border-destructive/30"}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {orphanOk ? <CheckCircle className="h-4 w-4 text-primary" /> : <AlertTriangle className="h-4 w-4 text-destructive" />}
            Integridad
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 p-4 rounded-lg bg-secondary/50 border border-border" data-testid="health-integrity">
            <div>
              <p className="text-xs text-muted-foreground font-mono">Líneas sin cabecera (pos_order_line sin pos_order)</p>
              <p className={`text-3xl font-bold font-mono mt-1 ${orphanOk ? "text-primary" : "text-destructive"}`}>
                {data?.orphan_lines?.toLocaleString() ?? "—"}
              </p>
            </div>
            {orphanOk ? (
              <Badge className="bg-primary/20 text-primary border-primary/30 text-xs font-mono">OK</Badge>
            ) : (
              <Badge variant="destructive" className="text-xs font-mono">ALERTA</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent Errors */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <XCircle className="h-4 w-4 text-destructive" /> Últimos Errores ({data?.recent_errors?.length || 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(data?.recent_errors || []).length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-xs">ID</TableHead>
                  <TableHead className="font-mono text-xs">Job</TableHead>
                  <TableHead className="font-mono text-xs">Empresa</TableHead>
                  <TableHead className="font-mono text-xs">Fecha</TableHead>
                  <TableHead className="font-mono text-xs">Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_errors.map((e) => (
                  <TableRow key={e.id} data-testid={`health-error-${e.id}`}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{e.id}</TableCell>
                    <TableCell className="font-mono text-sm text-primary">{e.job_code}</TableCell>
                    <TableCell className="font-mono text-sm">{e.company_key}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{fmtDate(e.started_at)}</TableCell>
                    <TableCell className="text-xs text-destructive max-w-[400px] truncate">{e.error_message || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground py-6 text-center">Sin errores recientes.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
