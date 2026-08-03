export const fmt = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("es-PE"));

export const fmt2 = (n) =>
  n === null || n === undefined
    ? "—"
    : Number(n).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const short = (n) => {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M";
  if (v >= 1e3) return Math.round(v / 1e3) + "K";
  return String(v);
};

export const ago = (iso) => {
  if (!iso) return "—";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "ahora";
  if (mins < 60) return `${mins} min`;
  if (mins < 1440) return `${Math.round(mins / 60)} h`;
  return `${Math.round(mins / 1440)} d`;
};

export const abs = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  const p = (x) => String(x).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
