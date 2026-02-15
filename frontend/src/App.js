import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import axios from "axios";
import { Toaster, toast } from "sonner";
import Dashboard from "@/pages/Dashboard";
import LogsPage from "@/pages/LogsPage";
import LocationsPage from "@/pages/LocationsPage";
import PosLinesPage from "@/pages/PosLinesPage";
import HealthPage from "@/pages/HealthPage";
import StockQuantsPage from "@/pages/StockQuantsPage";
import StockByProductPage from "@/pages/StockByProductPage";
import StockByLocationPage from "@/pages/StockByLocationPage";
import CreditInvoicesPage from "@/pages/CreditInvoicesPage";
import { Database } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [connection, setConnection] = useState(null);
  const [migrationStatus, setMigrationStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const [connRes, statusRes] = await Promise.all([
        axios.get(`${API}/connection/test`),
        axios.get(`${API}/migration/status`),
      ]);
      setConnection(connRes.data);
      setMigrationStatus(statusRes.data);
    } catch (e) {
      console.error("Error fetching status:", e);
      setConnection({ connected: false, error: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleMigrate = async () => {
    toast.info("Ejecutando migración...");
    try {
      const res = await axios.post(`${API}/migrate`);
      if (res.data.success) {
        toast.success(`Migración completada en ${res.data.duration_ms}ms`);
      } else {
        toast.error(`Error: ${res.data.message}`);
      }
      await fetchStatus();
    } catch (e) {
      toast.error(`Error de conexión: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-background bg-radial-glow">
      <Toaster theme="dark" position="top-right" richColors />
      <BrowserRouter>
        <nav className="border-b border-border sticky top-0 z-50 bg-background/80 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Database className="h-5 w-5 text-primary" />
                  <span
                    className="font-bold text-base tracking-tight"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    data-testid="app-title"
                  >
                    odoo<span className="text-primary">.</span>ODS
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <NavLink
                    to="/"
                    end
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-panel"
                  >
                    Panel
                  </NavLink>
                  <NavLink
                    to="/logs"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-logs"
                  >
                    Historial
                  </NavLink>
                  <NavLink
                    to="/locations"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-locations"
                  >
                    Locations
                  </NavLink>
                  <NavLink
                    to="/pos-lines"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-pos-lines"
                  >
                    POS Lines
                  </NavLink>
                  <NavLink
                    to="/stock-quants"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-stock-quants"
                  >
                    Stock Quants
                  </NavLink>
                  <NavLink
                    to="/stock-by-product"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-stock-product"
                  >
                    Stock x Producto
                  </NavLink>
                  <NavLink
                    to="/stock-by-location"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-stock-location"
                  >
                    Stock x Tienda
                  </NavLink>
                  <NavLink
                    to="/health"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-health"
                  >
                    Health
                  </NavLink>
                  <NavLink
                    to="/credit-invoices"
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                      }`
                    }
                    data-testid="nav-credit"
                  >
                    Créditos
                  </NavLink>
                </div>
              </div>
              <div className="flex items-center gap-3" data-testid="connection-status">
                {loading ? (
                  <span className="text-xs text-muted-foreground">Conectando...</span>
                ) : connection?.connected ? (
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                    </span>
                    <span className="text-xs text-muted-foreground font-mono-data">
                      PostgreSQL
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-destructive"></span>
                    <span className="text-xs text-destructive">Desconectado</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route
              path="/"
              element={
                <Dashboard
                  connection={connection}
                  migrationStatus={migrationStatus}
                  onMigrate={handleMigrate}
                  onRefresh={fetchStatus}
                  api={API}
                />
              }
            />
            <Route path="/logs" element={<LogsPage api={API} />} />
            <Route path="/locations" element={<LocationsPage api={API} />} />
            <Route path="/pos-lines" element={<PosLinesPage api={API} />} />
            <Route path="/stock-quants" element={<StockQuantsPage api={API} />} />
            <Route path="/stock-by-product" element={<StockByProductPage api={API} />} />
            <Route path="/stock-by-location" element={<StockByLocationPage api={API} />} />
            <Route path="/credit-invoices" element={<CreditInvoicesPage />} />
            <Route path="/health" element={<HealthPage api={API} />} />
          </Routes>
        </main>
      </BrowserRouter>
    </div>
  );
}

export default App;
