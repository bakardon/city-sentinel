"use client";

import { create } from "zustand";

export type TestModuleKey = "fire" | "knife" | "weapon" | "violence" | "accident";

export interface TestHistoryItem {
  id: string;
  module: TestModuleKey;
  kind: "image" | "video";
  filename: string;
  label?: string | null;
  confidence?: number | null;
  positive: boolean;
  ok: boolean;
  error?: string | null;
  snapshot_url?: string | null;
  clip_url?: string | null;
  created_at: number;
}

const MAX_ITEMS_PER_MODULE = 30;

interface TestHistoryState {
  items: TestHistoryItem[];
  addItem: (item: Omit<TestHistoryItem, "id" | "created_at">) => void;
  clear: (module?: TestModuleKey) => void;
}

export const useTestHistory = create<TestHistoryState>()((set) => ({
  items: [],
  addItem: (payload) =>
    set((s) => {
      const item: TestHistoryItem = {
        ...payload,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        created_at: Date.now(),
      };
      const forModule = s.items.filter((x) => x.module === payload.module);
      const rest = s.items.filter((x) => x.module !== payload.module);
      const next = [item, ...forModule].slice(0, MAX_ITEMS_PER_MODULE);
      return { items: [...next, ...rest] };
    }),
  clear: (module) =>
    set((s) => ({
      items: module ? s.items.filter((x) => x.module !== module) : [],
    })),
}));

export function isPositiveLabel(label?: string | null): boolean {
  if (!label) return false;
  const l = label.trim().toLowerCase();
  if (/^(non[-_\s]?|no[-_\s])/.test(l)) return false;
  return /fire|smoke|knife|weapon|gun|handgun|pistol|rifle|shotgun|heavyweapon|violence|fight|accident|crash|collision/i.test(l);
}
