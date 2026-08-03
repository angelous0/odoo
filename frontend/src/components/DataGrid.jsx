import { cn } from "@/lib/utils";

/**
 * Reusable compact spreadsheet-style grid.
 * cols: [{ key, label, align: 'left'|'right', width: number|'flex', sortable, sortDir }]
 * rows: [{ key, onClick, highlight, cells: [{ value, align, tone: 'default'|'muted'|'primary'|'danger'|'warn', strong, badge: 'emerald'|'neutral'|'danger'|'amber' }] }]
 */
export default function DataGrid({ cols, rows, onSort, minWidth = 560, emptyLabel = "Sin datos." }) {
  const colStyle = (c) =>
    c.width === "flex" ? { flex: "1 1 150px", minWidth: "150px" } : { flex: `0 0 ${c.width}px`, width: `${c.width}px` };

  return (
    <div
      className="w-full overflow-x-auto rounded-[10px] border"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      <div style={{ minWidth: `${minWidth}px` }}>
        <div className="flex sticky top-0 z-[2]" style={{ background: "var(--headrow)" }}>
          {cols.map((c) => (
            <div
              key={c.key}
              onClick={c.sortable ? () => onSort?.(c.key) : undefined}
              className={cn(
                "px-3 h-8 leading-8 whitespace-nowrap select-none border-b overflow-hidden text-ellipsis",
                c.sortable && "cursor-pointer"
              )}
              style={{
                textAlign: c.align || "left",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "9.5px",
                fontWeight: 700,
                letterSpacing: ".05em",
                textTransform: "uppercase",
                color: "var(--muted)",
                borderColor: "var(--border2)",
                ...colStyle(c),
              }}
            >
              {c.label}
              {c.sortable && c.sortDir ? (c.sortDir === "asc" ? "  ↑" : "  ↓") : ""}
            </div>
          ))}
        </div>
        {rows.length === 0 ? (
          <div className="text-center py-10 text-sm" style={{ color: "var(--muted2)" }}>
            {emptyLabel}
          </div>
        ) : (
          rows.map((row, i) => (
            <div
              key={row.key ?? i}
              onClick={row.onClick}
              className={cn("flex border-b group", row.onClick && "cursor-pointer")}
              style={{
                borderColor: "var(--border)",
                background: row.highlight ? "var(--dangerWeak)" : "transparent",
              }}
              onMouseEnter={(e) => {
                if (!row.highlight) e.currentTarget.style.background = "var(--rowHover)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = row.highlight ? "var(--dangerWeak)" : "transparent";
              }}
            >
              {row.cells.map((c, j) => (
                <div
                  key={j}
                  className="px-3 h-[31px] leading-[31px] overflow-hidden text-ellipsis whitespace-nowrap"
                  style={{ textAlign: c.align || cols[j]?.align || "left", ...colStyle(cols[j] || {}) }}
                >
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: "11.5px",
                      fontWeight: c.strong ? 600 : 500,
                      color: toneColor(c.tone),
                    }}
                  >
                    {c.badge ? <Badge kind={c.badge}>{c.value}</Badge> : c.value ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function toneColor(tone) {
  switch (tone) {
    case "muted":
      return "var(--muted)";
    case "primary":
      return "var(--primary)";
    case "danger":
      return "var(--danger)";
    case "warn":
      return "var(--warn)";
    default:
      return "var(--fg)";
  }
}

export function Badge({ kind = "neutral", children }) {
  const map = {
    emerald: ["var(--primaryWeak)", "var(--primaryText)", "transparent"],
    neutral: ["var(--card2)", "var(--muted)", "var(--border)"],
    danger: ["var(--dangerWeak)", "var(--danger)", "transparent"],
    amber: ["var(--warnWeak)", "var(--warn)", "transparent"],
  };
  const [bg, fg, border] = map[kind] || map.neutral;
  return (
    <span
      className="inline-block px-[7px] py-[2px] rounded-[5px]"
      style={{
        background: bg,
        color: fg,
        border: `1px solid ${border}`,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: "9.5px",
        fontWeight: 700,
        letterSpacing: ".03em",
      }}
    >
      {children}
    </span>
  );
}
