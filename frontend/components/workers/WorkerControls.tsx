"use client";

import { useState } from "react";
import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusPill } from "@/components/common/StatusPill";
import { CameraPresetPicker } from "@/components/workers/CameraPresetPicker";
import { formatRelativeTime } from "@/lib/utils";
import type { DetectionWorkerStatus, AccidentWorkerStatus } from "@/lib/types";

type AnyStatus = DetectionWorkerStatus | AccidentWorkerStatus;

interface WorkerControlsProps {
  title: string;
  status?: AnyStatus;
  onStart: (payload: { rtsp_url?: string; camera_id?: string; camera_location?: string }) => void;
  onStop: () => void;
  isStarting?: boolean;
  isStopping?: boolean;
  showLocation?: boolean;
}

export function WorkerControls({
  title,
  status,
  onStart,
  onStop,
  isStarting,
  isStopping,
  showLocation,
}: WorkerControlsProps) {
  const running = !!status?.running;
  const state = running ? "running" : status?.last_error ? "error" : "stopped";

  const [picker, setPicker] = useState({
    rtsp_url: "",
    camera_id: "",
    camera_location: "",
  });

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold">{title}</h3>
            <StatusPill state={state} label={running ? "RUNNING" : "STOPPED"} />
          </div>
          <div className="flex items-center gap-2">
            {!running ? (
              <Button
                size="sm"
                onClick={() =>
                  onStart({
                    rtsp_url: picker.rtsp_url || undefined,
                    camera_id: picker.camera_id || undefined,
                    camera_location: showLocation ? picker.camera_location || undefined : undefined,
                  })
                }
                disabled={isStarting}
              >
                <Play className="h-3.5 w-3.5" />
                {isStarting ? "Starting…" : "Start"}
              </Button>
            ) : (
              <Button size="sm" variant="destructive" onClick={onStop} disabled={isStopping}>
                <Square className="h-3.5 w-3.5" />
                {isStopping ? "Stopping…" : "Stop"}
              </Button>
            )}
          </div>
        </div>

        <CameraPresetPicker
          value={picker}
          onChange={setPicker}
          disabled={running}
          showLocation={showLocation}
        />

        <div className="grid gap-3 md:grid-cols-3">
          <InfoCell
            label="Last Frame"
            value={formatRelativeTime(status?.last_frame_utc ?? null)}
          />
          <InfoCell
            label="Last Alert"
            value={formatRelativeTime(status?.last_alert_utc ?? null)}
          />
          <InfoCell label="Alerts Seen" value={String(status?.alerts_seen ?? 0)} />
        </div>

        {!showLocation &&
        (status as AccidentWorkerStatus | undefined)?.last_supabase_snapshot_url ? (
          <InfoCell
            label="Last Snapshot"
            value={(status as AccidentWorkerStatus).last_supabase_snapshot_url || "-"}
            href={(status as AccidentWorkerStatus).last_supabase_snapshot_url}
          />
        ) : null}

        {status?.last_error ? (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {status.last_error}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function InfoCell({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href?: string | null;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/40 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block truncate font-mono text-xs text-primary hover:underline"
        >
          {value}
        </a>
      ) : (
        <div className="mt-1 truncate font-mono text-xs text-foreground/90">{value}</div>
      )}
    </div>
  );
}
