"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";
import { useServerUrl } from "@/lib/stores/serverUrl";

export function useHealth(intervalMs = 5000) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["health", server],
    queryFn: () => apiGet<{ status: string }>(endpoints.health),
    refetchInterval: intervalMs,
    retry: 0,
  });
}
