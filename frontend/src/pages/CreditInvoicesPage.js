import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const API = process.env.REACT_APP_BACKEND_URL;
const fmtNum = (v) => v != null ? Number(v).toLocaleString("es-PE", { minimumFractionDigits: 2 }) : "—";
const stateColors = { draft: "secondary", open: "default", paid: "outline", cancel: "destructive" };

export default function CreditInvoicesPage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [filters, setFilters] = useState({ company_key: "", date_from: "", date_to: "", state: "" });
  const pageSize = 50;

  const load = useCallback(() => {
    const params = new URLSearchParams({ page, page_size: pageSize });
    if (filters.company_key) params.set("company_key", filters.company_key);
    if (filters.date_from) params.set("date_from", filters.date_from);
    if (filters.date_to) params.set("date_to", filters.date_to);
    if (filters.state) params.set("state", filters.state);
    fetch(`${API}/api/credit-invoices?${params}`)
      .then((r) => r.json())
      .then((d) => { setRows(d.rows || []); setTotal(d.total || 0); setTotalPages(d.total_pages || 0); });
  }, [page, filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6" data-testid="credit-invoices-page">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tighter">Créditos</h1>
          <p className="text-sm text-muted-foreground font-mono">odoo.account_invoice_credit — {total.toLocaleString()} registros</p>
        </div>
        <Button variant="outline" onClick={() => { setPage(1); load(); }} data-testid="refresh-btn">Refrescar</Button>
      </div>

      <Card className="border-border/40">
        <CardHeader><CardTitle className="text-base font-semibold">Filtros</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-muted-foreground">Empresa</label>
            <Select value={filters.company_key} onValueChange={(v) => { setFilters((f) => ({ ...f, company_key: v === "ALL" ? "" : v })); setPage(1); }}>
              <SelectTrigger data-testid="filter-company"><SelectValue placeholder="Todas" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">Todas</SelectItem>
                <SelectItem value="Ambission">Ambission</SelectItem>
                <SelectItem value="ProyectoModa">ProyectoModa</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Desde</label>
            <Input type="date" value={filters.date_from} onChange={(e) => { setFilters((f) => ({ ...f, date_from: e.target.value })); setPage(1); }} data-testid="filter-date-from" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Hasta</label>
            <Input type="date" value={filters.date_to} onChange={(e) => { setFilters((f) => ({ ...f, date_to: e.target.value })); setPage(1); }} data-testid="filter-date-to" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Estado</label>
            <Select value={filters.state} onValueChange={(v) => { setFilters((f) => ({ ...f, state: v === "ALL" ? "" : v })); setPage(1); }}>
              <SelectTrigger data-testid="filter-state"><SelectValue placeholder="Todos" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">Todos</SelectItem>
                <SelectItem value="draft">Borrador</SelectItem>
                <SelectItem value="open">Abierto</SelectItem>
                <SelectItem value="paid">Pagado</SelectItem>
                <SelectItem value="cancel">Cancelado</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/40">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base font-semibold">Facturas de Crédito</CardTitle>
          <span className="text-xs text-muted-foreground font-mono">Pág {page}/{totalPages || 1}</span>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 justify-end mb-2">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} data-testid="prev-page">←</Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} data-testid="next-page">→</Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="font-mono text-xs">Empresa</TableHead>
                <TableHead className="font-mono text-xs">Número</TableHead>
                <TableHead className="font-mono text-xs">Fecha</TableHead>
                <TableHead className="font-mono text-xs">Cliente</TableHead>
                <TableHead className="font-mono text-xs">Estado</TableHead>
                <TableHead className="font-mono text-xs text-right">Total</TableHead>
                <TableHead className="font-mono text-xs text-right">Residual</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={`${r.company_key}-${r.odoo_id}`} data-testid={`credit-row-${r.odoo_id}`}>
                  <TableCell><Badge variant="outline" className="text-xs">{r.company_key}</Badge></TableCell>
                  <TableCell className="font-mono text-sm text-primary">{r.number || "—"}</TableCell>
                  <TableCell className="text-sm font-mono">{r.date_invoice || "—"}</TableCell>
                  <TableCell className="text-sm truncate max-w-[200px]">{r.partner_name || `#${r.partner_id}`}</TableCell>
                  <TableCell><Badge variant={stateColors[r.state] || "secondary"} className="text-xs">{r.state}</Badge></TableCell>
                  <TableCell className="text-right font-mono text-sm">{fmtNum(r.amount_total)}</TableCell>
                  <TableCell className="text-right font-mono text-sm font-medium">
                    <Badge variant={r.amount_residual > 0 ? "default" : "outline"} className="font-mono text-xs">
                      {fmtNum(r.amount_residual)}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">Sin datos. Ejecute la sincronización primero.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
