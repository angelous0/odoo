import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Play,
  RefreshCw,
  Database,
  TableProperties,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  Layers,
  Hash,
} from "lucide-react";

export const MetricCard = ({ title, value, icon: Icon, subtitle, delay }) => (
  <Card
    className={`animate-fade-up ${delay} border-border bg-card hover:bg-card/80 transition-colors`}
  >
    <CardContent className="p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
            {title}
          </p>
          <p
            className="text-2xl font-bold tracking-tight"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
          )}
        </div>
        <div className="p-2 rounded-md bg-secondary">
          <Icon className="h-4 w-4 text-primary" />
        </div>
      </div>
    </CardContent>
  </Card>
);

export const TablesTable = ({ tables }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead className="font-mono text-xs">Nombre</TableHead>
        <TableHead className="font-mono text-xs">Tipo</TableHead>
        <TableHead className="font-mono text-xs text-right">Filas</TableHead>
        <TableHead className="font-mono text-xs text-right">Columnas</TableHead>
        <TableHead className="font-mono text-xs text-center">Estado</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {tables.map((t) => (
        <TableRow key={t.name} data-testid={`table-row-${t.name}`}>
          <TableCell className="font-mono text-sm font-medium">
            <span className="text-muted-foreground">odoo.</span>
            {t.name}
          </TableCell>
          <TableCell>
            <Badge
              variant={t.type === "TABLE" ? "default" : "secondary"}
              className="text-[10px] font-mono"
            >
              {t.type === "TABLE" ? (
                <TableProperties className="h-3 w-3 mr-1" />
              ) : (
                <Eye className="h-3 w-3 mr-1" />
              )}
              {t.type}
            </Badge>
          </TableCell>
          <TableCell className="text-right font-mono text-sm">
            {t.type === "VIEW" ? "—" : t.row_count}
          </TableCell>
          <TableCell className="text-right font-mono text-sm">
            {t.col_count}
          </TableCell>
          <TableCell className="text-center">
            {t.exists ? (
              <CheckCircle className="h-4 w-4 text-primary mx-auto" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive mx-auto" />
            )}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

export const SyncJobsTable = ({ jobs }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead className="font-mono text-xs">Job Code</TableHead>
        <TableHead className="font-mono text-xs text-center">Habilitado</TableHead>
        <TableHead className="font-mono text-xs">Horario</TableHead>
        <TableHead className="font-mono text-xs">Modo</TableHead>
        <TableHead className="font-mono text-xs text-right">Prioridad</TableHead>
        <TableHead className="font-mono text-xs text-right">Chunk</TableHead>
        <TableHead className="font-mono text-xs">Scope</TableHead>
        <TableHead className="font-mono text-xs">Último Error</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {jobs.map((j) => (
        <TableRow key={j.job_code} data-testid={`job-row-${j.job_code}`}>
          <TableCell className="font-mono text-sm font-medium text-primary">
            {j.job_code}
          </TableCell>
          <TableCell className="text-center">
            {j.enabled ? (
              <CheckCircle className="h-4 w-4 text-primary mx-auto" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive mx-auto" />
            )}
          </TableCell>
          <TableCell className="font-mono text-sm">
            <span className="text-muted-foreground">{j.schedule_type}</span>
            <span className="ml-2">{j.run_time}</span>
          </TableCell>
          <TableCell>
            <Badge
              variant="secondary"
              className="text-[10px] font-mono"
            >
              {j.mode}
            </Badge>
          </TableCell>
          <TableCell className="text-right font-mono text-sm">{j.priority}</TableCell>
          <TableCell className="text-right font-mono text-sm">{j.chunk_size}</TableCell>
          <TableCell className="font-mono text-sm text-muted-foreground">
            {j.company_scope}
          </TableCell>
          <TableCell className="text-sm max-w-[200px] truncate">
            {j.last_error ? (
              <span className="text-destructive">{j.last_error}</span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

export const IndexesTable = ({ indexes }) => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead className="font-mono text-xs">Índice</TableHead>
        <TableHead className="font-mono text-xs">Tabla</TableHead>
        <TableHead className="font-mono text-xs">Definición</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {indexes.map((idx, i) => (
        <TableRow key={i} data-testid={`index-row-${idx.indexname}`}>
          <TableCell className="font-mono text-xs text-primary">
            {idx.indexname}
          </TableCell>
          <TableCell className="font-mono text-xs text-muted-foreground">
            {idx.tablename}
          </TableCell>
          <TableCell className="font-mono text-[11px] text-muted-foreground max-w-[500px] truncate">
            {idx.indexdef}
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

export default function Dashboard({
  connection,
  migrationStatus,
  onMigrate,
  onRefresh,
  api,
}) {
  const [tables, setTables] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [indexes, setIndexes] = useState([]);
  const [migrating, setMigrating] = useState(false);
  const [activeTab, setActiveTab] = useState("tables");

  const fetchData = useCallback(async () => {
    try {
      const [tablesRes, jobsRes, indexesRes] = await Promise.all([
        axios.get(`${api}/schema/tables`),
        axios.get(`${api}/sync-jobs`),
        axios.get(`${api}/schema/indexes`),
      ]);
      setTables(tablesRes.data.tables || []);
      setJobs(jobsRes.data.jobs || []);
      setIndexes(indexesRes.data.indexes || []);
    } catch (e) {
      console.error("Error fetching data:", e);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleMigrate = async () => {
    setMigrating(true);
    await onMigrate();
    await fetchData();
    setMigrating(false);
  };

  const handleRefresh = async () => {
    await onRefresh();
    await fetchData();
  };

  const totalTables = tables.filter((t) => t.type === "TABLE" && t.exists).length;
  const totalViews = tables.filter((t) => t.type === "VIEW" && t.exists).length;
  const totalRows = tables.reduce((acc, t) => acc + (t.row_count || 0), 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1
            className="text-3xl md:text-4xl font-bold tracking-tight"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
            data-testid="dashboard-title"
          >
            Panel de Migración
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Schema <code className="text-primary font-mono">odoo</code> en PostgreSQL &mdash; ODS para sincronización
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            data-testid="refresh-btn"
            aria-label="Refrescar datos"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refrescar
          </Button>
          <Button
            size="sm"
            onClick={handleMigrate}
            disabled={migrating}
            className={`shadow-[0_0_15px_rgba(16,185,129,0.3)] ${
              migrating ? "animate-pulse-glow" : ""
            }`}
            data-testid="migrate-btn"
            aria-label="Ejecutar migración"
          >
            <Play className="h-4 w-4 mr-2" />
            {migrating ? "Ejecutando..." : "Ejecutar Migración"}
          </Button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Tablas"
          value={totalTables}
          icon={TableProperties}
          subtitle={`de ${migrationStatus?.tables_expected || 0} esperadas`}
          delay="animate-fade-up-1"
          data-testid="metric-tables"
        />
        <MetricCard
          title="Vistas"
          value={totalViews}
          icon={Eye}
          subtitle={`de ${migrationStatus?.views_expected || 0} esperadas`}
          delay="animate-fade-up-2"
          data-testid="metric-views"
        />
        <MetricCard
          title="Índices"
          value={migrationStatus?.indexes_count || 0}
          icon={Hash}
          subtitle="en schema odoo"
          delay="animate-fade-up-3"
          data-testid="metric-indexes"
        />
        <MetricCard
          title="Estado"
          value={migrationStatus?.all_ok ? "OK" : "Pendiente"}
          icon={migrationStatus?.all_ok ? CheckCircle : Clock}
          subtitle={
            migrationStatus?.all_ok
              ? "Todas las tablas creadas"
              : "Ejecutar migración"
          }
          delay="animate-fade-up-4"
          data-testid="metric-status"
        />
      </div>

      {/* Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-secondary" data-testid="tabs-list">
          <TabsTrigger value="tables" data-testid="tab-tables">
            <Database className="h-3.5 w-3.5 mr-1.5" />
            Tablas ({tables.length})
          </TabsTrigger>
          <TabsTrigger value="jobs" data-testid="tab-jobs">
            <Clock className="h-3.5 w-3.5 mr-1.5" />
            Sync Jobs ({jobs.length})
          </TabsTrigger>
          <TabsTrigger value="indexes" data-testid="tab-indexes">
            <Layers className="h-3.5 w-3.5 mr-1.5" />
            Índices ({indexes.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="tables" data-testid="tab-content-tables">
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <CardTitle
                className="text-base font-medium"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Tablas y Vistas del Schema odoo
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tables.length > 0 ? (
                <TablesTable tables={tables} />
              ) : (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No se encontraron tablas. Ejecuta la migración.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="jobs" data-testid="tab-content-jobs">
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <CardTitle
                className="text-base font-medium"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Trabajos de Sincronización
              </CardTitle>
            </CardHeader>
            <CardContent>
              {jobs.length > 0 ? (
                <SyncJobsTable jobs={jobs} />
              ) : (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No hay jobs configurados. Ejecuta la migración.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="indexes" data-testid="tab-content-indexes">
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <CardTitle
                className="text-base font-medium"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Índices del Schema odoo
              </CardTitle>
            </CardHeader>
            <CardContent>
              {indexes.length > 0 ? (
                <IndexesTable indexes={indexes} />
              ) : (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No se encontraron índices.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
