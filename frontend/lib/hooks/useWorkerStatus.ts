"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { endpoints, type DetectionModule } from "@/lib/endpoints";
import { useServerUrl } from "@/lib/stores/serverUrl";
import type { AccidentWorkerStatus, DetectionWorkerStatus } from "@/lib/types";

interface StatusEnvelope<T> {
  status: T;
}

export function useDetectionWorkerStatus(module: DetectionModule, intervalMs = 2500) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["worker-status", module, server],
    queryFn: () => apiGet<StatusEnvelope<DetectionWorkerStatus>>(endpoints.worker(module).status),
    refetchInterval: intervalMs,
    select: (r) => r.status,
  });
}

export function useAccidentWorkerStatus(intervalMs = 2500) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["accident-worker-status", server],
    queryFn: () => apiGet<StatusEnvelope<AccidentWorkerStatus>>(endpoints.accidentWorker.status),
    refetchInterval: intervalMs,
    select: (r) => r.status,
  });
}
