"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export const DEFAULT_SERVER_URL = "http://127.0.0.1:8010";

interface ServerUrlState {
  url: string;
  setUrl: (next: string) => void;
  reset: () => void;
}

export const useServerUrl = create<ServerUrlState>()(
  persist(
    (set) => ({
      url: DEFAULT_SERVER_URL,
      setUrl: (next) => set({ url: (next || DEFAULT_SERVER_URL).replace(/\/$/, "") }),
      reset: () => set({ url: DEFAULT_SERVER_URL }),
    }),
    {
      name: "city-sentinel.serverUrl",
      version: 1,
    }
  )
);

export function getServerUrlSnapshot(): string {
  if (typeof window === "undefined") return DEFAULT_SERVER_URL;
  const raw = localStorage.getItem("city-sentinel.serverUrl");
  if (!raw) return DEFAULT_SERVER_URL;
  try {
    const parsed = JSON.parse(raw) as { state?: { url?: string } };
    const v = parsed?.state?.url;
    return typeof v === "string" && v ? v.replace(/\/$/, "") : DEFAULT_SERVER_URL;
  } catch {
    return DEFAULT_SERVER_URL;
  }
}
