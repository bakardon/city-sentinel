"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { endpoints, type DetectionModule } from "@/lib/endpoints";
import { useServerUrl } from "@/lib/stores/serverUrl";
import type { WorkerFrame } from "@/lib/types";

export function useWorkerFrame(module: DetectionModule, opts?: { enabled?: boolean; intervalMs?: number }) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["worker-frame", module, server],
    queryFn: () => apiGet<WorkerFrame>(endpoints.worker(module).frame),
    refetchInterval: opts?.intervalMs ?? 1000,
    enabled: opts?.enabled ?? true,
    staleTime: 0,
  });
}
