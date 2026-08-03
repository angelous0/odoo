import { createContext, useContext } from "react";

export const GotoTableContext = createContext(() => {});

export function useGotoTable() {
  return useContext(GotoTableContext);
}
