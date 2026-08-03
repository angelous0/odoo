const KEY = "ods_theme";

export function getInitialTheme() {
  try {
    const s = localStorage.getItem(KEY);
    if (s === "light" || s === "dark") return s;
  } catch (e) {}
  return "light";
}

export function applyTheme(theme) {
  try {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(KEY, theme);
  } catch (e) {}
}
