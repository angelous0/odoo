import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RefreshCw, Package, ChevronLeft, ChevronRight } from "lucide-react";

const fmtDate = (iso) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};
const fmtNum = (v) => v === null || v === undefined ? "—" : Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 4 });

export default function StockQuantsPage({ api }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [productId, setProductId] = useState("");
  const [locationId, setLocationId] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 50 };
      if (productId.trim()) params.product_id = productId.trim();
      if (locationId.trim()) params.location_id = locationId.trim();
      const res = await axios.get(`${api}/stock-quants`, { params });
      setRows(res.data.rows || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.total_pages || 0);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [api, page, productId, locationId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="stock-quants-title">
            Stock Quants
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            <code className="text-primary font-mono">odoo.stock_quant</code> &mdash; {total.toLocaleString()} registros (GLOBAL)
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} data-testid="refresh-stock-quants-btn">
          <RefreshCw className="h-4 w-4 mr-2" />Refrescar
        </Button>
      </div>

      <Card className="border-border bg-card">
        <CardContent className="pt-4">
          <div className="flex gap-3 mb-4">
            <Input placeholder="product_id" value={productId} onChange={(e) => { setProductId(e.target.value); setPage(1); }}
              className="h-8 text-xs bg-secondary w-[140px]" data-testid="filter-product-id" />
            <Input placeholder="location_id" value={locationId} onChange={(e) => { setLocationId(e.target.value); setPage(1); }}
              className="h-8 text-xs bg-secondary w-[140px]" data-testid="filter-location-id" />
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <Package className="h-4 w-4 text-primary" /> Quants
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
                  <TableHead className="font-mono text-xs">odoo_id</TableHead>
                  <TableHead className="font-mono text-xs text-right">product_id</TableHead>
                  <TableHead className="font-mono text-xs text-right">location_id</TableHead>
                  <TableHead className="font-mono text-xs text-right">qty</TableHead>
                  <TableHead className="font-mono text-xs text-right">reserved_qty</TableHead>
                  <TableHead className="font-mono text-xs">in_date</TableHead>
                  <TableHead className="font-mono text-xs">write_date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.odoo_id} data-testid={`quant-row-${r.odoo_id}`}>
                    <TableCell className="font-mono text-sm text-primary">{r.odoo_id}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{r.product_id}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-muted-foreground">{r.location_id}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{fmtNum(r.qty)}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-muted-foreground">{fmtNum(r.reserved_qty)}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{fmtDate(r.in_date)}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{fmtDate(r.odoo_write_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <Package className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Sin datos. Ejecuta sync STOCK_QUANTS.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
