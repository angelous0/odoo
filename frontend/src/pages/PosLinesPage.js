import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RefreshCw, ShoppingCart, ChevronLeft, ChevronRight, Filter, X } from "lucide-react";

const fmtDate = (iso) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

const fmtNum = (v, d = 2) => {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
};

const defaultDateFrom = () => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
};

export default function PosLinesPage({ api }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [companyKey, setCompanyKey] = useState("ALL");
  const [dateFrom, setDateFrom] = useState(defaultDateFrom());
  const [dateTo, setDateTo] = useState("");
  const [isCancelled, setIsCancelled] = useState("ALL");
  const [marca, setMarca] = useState("");
  const [tipo, setTipo] = useState("");
  const [tela, setTela] = useState("");
  const [talla, setTalla] = useState("");
  const [color, setColor] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 50 };
      if (companyKey !== "ALL") params.company_key = companyKey;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (isCancelled !== "ALL") params.is_cancelled = isCancelled === "YES";
      if (marca.trim()) params.marca = marca.trim();
      if (tipo.trim()) params.tipo = tipo.trim();
      if (tela.trim()) params.tela = tela.trim();
      if (talla.trim()) params.talla = talla.trim();
      if (color.trim()) params.color = color.trim();
      const res = await axios.get(`${api}/pos-lines-full`, { params });
      setRows(res.data.rows || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [api, page, companyKey, dateFrom, dateTo, isCancelled, marca, tipo, tela, talla, color]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const resetFilters = () => {
    setCompanyKey("ALL"); setDateFrom(defaultDateFrom()); setDateTo("");
    setIsCancelled("ALL"); setMarca(""); setTipo(""); setTela(""); setTalla(""); setColor("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="pos-lines-title">
            POS Lines Full
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            <code className="text-primary font-mono">odoo.v_pos_line_full</code> &mdash; {total.toLocaleString()} filas
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={resetFilters} data-testid="reset-filters-btn">
            <X className="h-4 w-4 mr-1" />Reset
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData} data-testid="refresh-pos-lines-btn">
            <RefreshCw className="h-4 w-4 mr-2" />Refrescar
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="border-border bg-card" data-testid="filters-panel">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <Filter className="h-3.5 w-3.5 text-primary" /> Filtros
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Empresa</label>
              <Select value={companyKey} onValueChange={(v) => { setCompanyKey(v); setPage(1); }}>
                <SelectTrigger className="h-8 text-xs bg-secondary" data-testid="filter-company">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Todas</SelectItem>
                  <SelectItem value="Ambission">Ambission</SelectItem>
                  <SelectItem value="ProyectoModa">ProyectoModa</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Desde</label>
              <Input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                className="h-8 text-xs bg-secondary" data-testid="filter-date-from" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Hasta</label>
              <Input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                className="h-8 text-xs bg-secondary" data-testid="filter-date-to" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Cancelado</label>
              <Select value={isCancelled} onValueChange={(v) => { setIsCancelled(v); setPage(1); }}>
                <SelectTrigger className="h-8 text-xs bg-secondary" data-testid="filter-cancelled">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Todos</SelectItem>
                  <SelectItem value="YES">Cancelados</SelectItem>
                  <SelectItem value="NO">No cancelados</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Marca</label>
              <Input value={marca} onChange={(e) => { setMarca(e.target.value); setPage(1); }}
                placeholder="Filtrar..." className="h-8 text-xs bg-secondary" data-testid="filter-marca" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Tipo</label>
              <Input value={tipo} onChange={(e) => { setTipo(e.target.value); setPage(1); }}
                placeholder="Filtrar..." className="h-8 text-xs bg-secondary" data-testid="filter-tipo" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Tela</label>
              <Input value={tela} onChange={(e) => { setTela(e.target.value); setPage(1); }}
                placeholder="Filtrar..." className="h-8 text-xs bg-secondary" data-testid="filter-tela" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Talla</label>
              <Input value={talla} onChange={(e) => { setTalla(e.target.value); setPage(1); }}
                placeholder="Filtrar..." className="h-8 text-xs bg-secondary" data-testid="filter-talla" />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground font-mono mb-1 block">Color</label>
              <Input value={color} onChange={(e) => { setColor(e.target.value); setPage(1); }}
                placeholder="Filtrar..." className="h-8 text-xs bg-secondary" data-testid="filter-color" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <ShoppingCart className="h-4 w-4 text-primary" /> Resultados
            </CardTitle>
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <span>Pág {page} / {totalPages}</span>
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1}
                onClick={() => setPage(p => p - 1)} data-testid="page-prev">
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)} data-testid="page-next">
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-[10px]">Empresa</TableHead>
                  <TableHead className="font-mono text-[10px]">Fecha</TableHead>
                  <TableHead className="font-mono text-[10px]">Estado</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">Orden</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">Línea</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">Qty</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">P.Unit</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">Desc%</TableHead>
                  <TableHead className="font-mono text-[10px] text-right">Subtotal</TableHead>
                  <TableHead className="font-mono text-[10px]">Barcode</TableHead>
                  <TableHead className="font-mono text-[10px]">Talla</TableHead>
                  <TableHead className="font-mono text-[10px]">Color</TableHead>
                  <TableHead className="font-mono text-[10px]">Marca</TableHead>
                  <TableHead className="font-mono text-[10px]">Tipo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={i} data-testid={`pos-line-row-${i}`}>
                    <TableCell className="text-xs">
                      <Badge variant={r.company_key === "Ambission" ? "default" : "secondary"} className="text-[9px] font-mono">
                        {r.company_key}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-muted-foreground whitespace-nowrap">{fmtDate(r.date_order)}</TableCell>
                    <TableCell>
                      {r.is_cancelled ? (
                        <Badge variant="destructive" className="text-[9px]">CANCEL</Badge>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">{r.state}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-muted-foreground">{r.order_id}</TableCell>
                    <TableCell className="text-right font-mono text-xs text-primary">{r.pos_order_line_id}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{fmtNum(r.qty, 0)}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{fmtNum(r.price_unit)}</TableCell>
                    <TableCell className="text-right font-mono text-xs text-muted-foreground">{fmtNum(r.discount)}</TableCell>
                    <TableCell className="text-right font-mono text-xs font-medium">{fmtNum(r.price_subtotal)}</TableCell>
                    <TableCell className="font-mono text-[11px] text-muted-foreground">{r.barcode || "—"}</TableCell>
                    <TableCell className="text-xs">{r.talla || "—"}</TableCell>
                    <TableCell className="text-xs">{r.color || "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.marca || "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.tipo || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <ShoppingCart className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Sin resultados. Ajusta los filtros.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
