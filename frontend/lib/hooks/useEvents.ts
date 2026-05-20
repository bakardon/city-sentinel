"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { endpoints, eventsEndpointFor, type DetectionModule } from "@/lib/endpoints";
import { useServerUrl } from "@/lib/stores/serverUrl";
import type {
  AccidentRecord,
  DetectionEvent,
  MissingAlert,
  VehiclesEventsResponse,
} from "@/lib/types";

interface EventsEnvelope {
  events: DetectionEvent[];
}

export function useDetectionEvents(
  module: DetectionModule,
  params?: { camera_id?: string; limit?: number },
  intervalMs = 8000
) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["events", module, params, server],
    queryFn: () =>
      apiGet<EventsEnvelope>(eventsEndpointFor(module), {
        camera_id: params?.camera_id,
        limit: params?.limit ?? 50,
      }),
    refetchInterval: intervalMs,
    select: (r) => r.events ?? [],
  });
}

export function useAccidents(
  params?: { camera_id?: string; limit?: number },
  intervalMs = 8000
) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["accidents", params, server],
    queryFn: () =>
      apiGet<{ accidents: AccidentRecord[] }>(endpoints.accidents, {
        camera_id: params?.camera_id,
        limit: params?.limit ?? 24,
      }),
    refetchInterval: intervalMs,
    select: (r) => r.accidents ?? [],
  });
}

export function useVehicleEvents(
  params?: { plate?: string; status?: string; start_time?: string; end_time?: string; limit?: number },
  intervalMs = 8000
) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["vehicles", params, server],
    queryFn: () =>
      apiGet<VehiclesEventsResponse>(endpoints.vehiclesEvents, {
        plate: params?.plate,
        status: params?.status,
        start_time: params?.start_time,
        end_time: params?.end_time,
        limit: params?.limit ?? 200,
      }),
    refetchInterval: intervalMs,
  });
}

export function useMissingAlerts(intervalMs = 10000) {
  const server = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["missing-alerts", server],
    queryFn: () => apiGet<{ alerts: MissingAlert[]; threshold_s: number }>(endpoints.missingAlerts),
    refetchInterval: intervalMs,
  });
}
