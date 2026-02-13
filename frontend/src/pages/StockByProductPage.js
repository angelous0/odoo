import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RefreshCw, BarChart3, ChevronLeft, ChevronRight, Filter } from "lucide-react";

const fmtNum = (v, d = 2) => v === null || v === undefined ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });

export default function StockByProductPage({ api }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [onlyAvailable, setOnlyAvailable] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 50 };
      if (onlyAvailable) params.only_available = true;
      const res = await axios.get(`${api}/stock-by-product`, { params });
      setRows(res.data.rows || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 0);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [api, page, onlyAvailable]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="stock-product-title">
            Stock x Producto
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            <code className="text-primary font-mono">odoo.v_stock_by_product</code> &mdash; {total.toLocaleString()} productos (internal locations)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant={onlyAvailable ? "default" : "outline"} size="sm"
            onClick={() => { setOnlyAvailable(!onlyAvailable); setPage(1); }}
            className={onlyAvailable ? "shadow-[0_0_10px_rgba(16,185,129,0.3)]" : ""}
            data-testid="toggle-available">
            <Filter className="h-4 w-4 mr-1.5" />
            {onlyAvailable ? "Solo disponible" : "Todos"}
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData} data-testid="refresh-stock-product-btn">
            <RefreshCw className="h-4 w-4 mr-2" />Refrescar
          </Button>
        </div>
      </div>

      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <BarChart3 className="h-4 w-4 text-primary" /> Stock Disponible
            </CardTitle>
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <span>Pág {page}/{totalPages}</span>
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1} onClick={() => setPage(p => p - 1)} data-testid="page-prev"><ChevronLeft className="h-3.5 w-3.5" /></Button>
              <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} data-testid="page-next"><ChevronRight className="h-3.5 w-3.5" /></Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12"><RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" /></div>
          ) : rows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-xs text-right">product_id</TableHead>
                  <TableHead className="font-mono text-xs text-right">qty</TableHead>
                  <TableHead className="font-mono text-xs text-right">reserved_qty</TableHead>
                  <TableHead className="font-mono text-xs text-right">available_qty</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.product_id} data-testid={`stock-prod-row-${r.product_id}`}>
                    <TableCell className="text-right font-mono text-sm text-primary">{r.product_id}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{fmtNum(r.qty)}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-muted-foreground">{fmtNum(r.reserved_qty)}</TableCell>
                    <TableCell className="text-right font-mono text-sm font-medium">
                      <Badge variant={r.available_qty > 0 ? "default" : "destructive"} className="font-mono text-xs">
                        {fmtNum(r.available_qty)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <BarChart3 className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Sin datos de stock.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
