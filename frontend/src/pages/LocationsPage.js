import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RefreshCw, MapPin, CheckCircle, XCircle } from "lucide-react";

export default function LocationsPage({ api }) {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/stock-locations`);
      setLocations(res.data.locations || []);
    } catch (e) {
      console.error("Error fetching locations:", e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetch(); }, [fetch]);

  const fmtDate = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("es-AR", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight"
            style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="locations-title">
            Locations
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            <code className="text-primary font-mono">odoo.stock_location</code> &mdash; company_key = GLOBAL
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetch} data-testid="refresh-locations-btn">
          <RefreshCw className="h-4 w-4 mr-2" />Refrescar
        </Button>
      </div>

      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <MapPin className="h-4 w-4 text-primary" />
            Tiendas / Ubicaciones ({locations.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Cargando...</span>
            </div>
          ) : locations.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-mono text-xs">ID</TableHead>
                  <TableHead className="font-mono text-xs">x_nombre</TableHead>
                  <TableHead className="font-mono text-xs">name</TableHead>
                  <TableHead className="font-mono text-xs">complete_name</TableHead>
                  <TableHead className="font-mono text-xs">usage</TableHead>
                  <TableHead className="font-mono text-xs text-center">Activo</TableHead>
                  <TableHead className="font-mono text-xs text-right">Parent ID</TableHead>
                  <TableHead className="font-mono text-xs text-right">Company</TableHead>
                  <TableHead className="font-mono text-xs">write_date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {locations.map((loc) => (
                  <TableRow key={loc.odoo_id} data-testid={`location-row-${loc.odoo_id}`}>
                    <TableCell className="font-mono text-sm text-primary">{loc.odoo_id}</TableCell>
                    <TableCell className="text-sm font-medium">{loc.x_nombre || "—"}</TableCell>
                    <TableCell className="font-mono text-sm">{loc.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground max-w-[250px] truncate">{loc.complete_name || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px] font-mono">{loc.usage}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {loc.active ? <CheckCircle className="h-4 w-4 text-primary mx-auto" /> : <XCircle className="h-4 w-4 text-destructive mx-auto" />}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm text-muted-foreground">{loc.location_id ?? "—"}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-muted-foreground">{loc.company_id ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{fmtDate(loc.odoo_write_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <MapPin className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No hay ubicaciones sincronizadas.</p>
              <p className="text-xs text-muted-foreground mt-1">Ejecuta el sync de STOCK_LOCATIONS desde el panel.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
