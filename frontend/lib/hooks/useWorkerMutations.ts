"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPostJson } from "@/lib/api";
import { endpoints, type DetectionModule } from "@/lib/endpoints";
import { toast } from "sonner";

interface StartPayload {
  rtsp_url?: string;
  camera_id?: string;
  camera_location?: string;
}

export function useDetectionWorkerMutations(module: DetectionModule) {
  const qc = useQueryClient();

  const start = useMutation({
    mutationFn: (payload: StartPayload) => apiPostJson(endpoints.worker(module).start, payload),
    onSuccess: () => {
      toast.success(`${module} worker start requested`);
      qc.invalidateQueries({ queryKey: ["worker-status", module] });
    },
    onError: (e: Error) => toast.error(e.message || `Failed to start ${module} worker`),
  });

  const stop = useMutation({
    mutationFn: () => apiPostJson(endpoints.worker(module).stop),
    onSuccess: () => {
      toast.success(`${module} worker stop requested`);
      qc.invalidateQueries({ queryKey: ["worker-status", module] });
    },
    onError: (e: Error) => toast.error(e.message || `Failed to stop ${module} worker`),
  });

  return { start, stop };
}

export function useAccidentWorkerMutations() {
  const qc = useQueryClient();

  const start = useMutation({
    mutationFn: (payload: StartPayload) => apiPostJson(endpoints.accidentWorker.start, payload),
    onSuccess: () => {
      toast.success("Accident worker start requested");
      qc.invalidateQueries({ queryKey: ["accident-worker-status"] });
    },
    onError: (e: Error) => toast.error(e.message || "Failed to start accident worker"),
  });

  const stop = useMutation({
    mutationFn: () => apiPostJson(endpoints.accidentWorker.stop),
    onSuccess: () => {
      toast.success("Accident worker stop requested");
      qc.invalidateQueries({ queryKey: ["accident-worker-status"] });
    },
    onError: (e: Error) => toast.error(e.message || "Failed to stop accident worker"),
  });

  return { start, stop };
}
