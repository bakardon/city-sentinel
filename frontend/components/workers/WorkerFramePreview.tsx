"use client";

import { AlertTriangle, Eye } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusPill } from "@/components/common/StatusPill";
import { useWorkerFrame } from "@/lib/hooks/useWorkerFrame";
import { formatRelativeTime } from "@/lib/utils";
import type { DetectionModule } from "@/lib/endpoints";

interface WorkerFramePreviewProps {
  module: DetectionModule;
  title?: string;
  enabled?: boolean;
}

export function WorkerFramePreview({
  module,
  title = "Live Preview",
  enabled = true,
}: WorkerFramePreviewProps) {
  const { data, isError, error } = useWorkerFrame(module, { enabled });
  const b64 = (data?.image_b64 as string | undefined) || "";
  const stale = !!data?.stale;
  const ts = typeof data?.ts === "number" ? data.ts : null;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">{title}</span>
          </div>
          <StatusPill
            state={isError || data?.error ? "error" : b64 ? (stale ? "idle" : "running") : "stopped"}
            label={
              isError
                ? "ERROR"
                : data?.error
                ? "ERROR"
                : b64
                ? stale
                  ? "STALE"
                  : "LIVE"
                : "NO FRAME"
            }
          />
        </div>
        <div className="relative aspect-video w-full overflow-hidden rounded-md border border-border/60 bg-black">
          {b64 ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/jpeg;base64,${b64}`}
              alt={`${module} frame`}
              className="h-full w-full object-contain"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Worker not sending frames
            </div>
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
          <span>Updated {formatRelativeTime(ts)}</span>
          {(isError || data?.error) && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <AlertTriangle className="h-3.5 w-3.5" />
              {(error as Error | null)?.message || String(data?.error || "Unknown error")}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
