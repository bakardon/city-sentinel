"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Camera, Crosshair, Play, RefreshCw, Square, Swords } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { WorkerControls } from "@/components/workers/WorkerControls";
import { WorkerFramePreview } from "@/components/workers/WorkerFramePreview";
import { EventCard } from "@/components/common/EventCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiPostForm } from "@/lib/api";
import { useDetectionWorkerStatus } from "@/lib/hooks/useWorkerStatus";
import { useDetectionWorkerMutations } from "@/lib/hooks/useWorkerMutations";
import { useDetectionEvents } from "@/lib/hooks/useEvents";
import type { DetectionEvent } from "@/lib/types";

type ArmedModule = "knife" | "weapon";

function useArmedEvents(cameraId?: string) {
  const knife = useDetectionEvents("knife", { camera_id: cameraId });
  const weapon = useDetectionEvents("weapon", { camera_id: cameraId });

  const merged = useMemo(() => {
    const withKind = [
      ...(knife.data ?? []).map((e) => ({ ...e, _module: "knife" as const })),
      ...(weapon.data ?? []).map((e) => ({ ...e, _module: "weapon" as const })),
    ];
    withKind.sort((a, b) => {
      const ta = a.event_time ? Date.parse(a.event_time) : 0;
      const tb = b.event_time ? Date.parse(b.event_time) : 0;
      return tb - ta;
    });
    return withKind;
  }, [knife.data, weapon.data]);

  return {
    events: merged,
    isFetching: knife.isFetching || weapon.isFetching,
    refetch: () => {
      knife.refetch();
      weapon.refetch();
    },
  };
}

export default function ArmedDetectionPage() {
  const [cameraFilter, setCameraFilter] = useState("");
  const [appliedCamera, setAppliedCamera] = useState<string | undefined>(undefined);
  const [moduleFilter, setModuleFilter] = useState<ArmedModule | "all">("all");

  const { events, isFetching, refetch } = useArmedEvents(appliedCamera);

  const visible = useMemo(
    () => (moduleFilter === "all" ? events : events.filter((e) => e._module === moduleFilter)),
    [events, moduleFilter]
  );

  return (
    <>
      <PageHeader
        title="Armed Threat Detection"
        description="Unified surveillance for bladed weapons and firearms. Two dedicated workers, two live streams, one combined incident feed."
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ModuleColumn module="knife" label="Knife" icon={<Swords className="h-4 w-4" />} />
        <ModuleColumn module="weapon" label="Firearm" icon={<Crosshair className="h-4 w-4" />} />
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 space-y-0 border-b border-border/60 py-4 md:flex-row md:items-center md:justify-between">
          <CardTitle className="flex items-center gap-3 text-sm">
            Combined Threat Feed
            <div className="flex items-center gap-1">
              <FilterChip active={moduleFilter === "all"} onClick={() => setModuleFilter("all")}>
                All
              </FilterChip>
              <FilterChip active={moduleFilter === "knife"} onClick={() => setModuleFilter("knife")}>
                Knife
              </FilterChip>
              <FilterChip active={moduleFilter === "weapon"} onClick={() => setModuleFilter("weapon")}>
                Firearm
              </FilterChip>
            </div>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Input
              value={cameraFilter}
              onChange={(e) => setCameraFilter(e.target.value)}
              placeholder="camera_id (optional)"
              className="h-8 w-48 font-mono text-xs"
            />
            <Button
              size="sm"
              variant="secondary"
              className="h-8"
              onClick={() => {
                setAppliedCamera(cameraFilter || undefined);
                refetch();
              }}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-5">
          {visible.length === 0 ? (
            <div className="flex h-28 items-center justify-center rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
              No armed-threat events recorded.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {visible.map((e) => (
                <ArmedEventCard key={`${e._module}-${String(e.id)}`} event={e} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function ModuleColumn({
  module,
  label,
  icon,
}: {
  module: ArmedModule;
  label: string;
  icon: React.ReactNode;
}) {
  const { data: status } = useDetectionWorkerStatus(module);
  const { start, stop } = useDetectionWorkerMutations(module);
  const running = !!status?.running;
  const [previewSource, setPreviewSource] = useState<"rtsp" | "webcam">("rtsp");

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/30">
          {icon}
        </span>
        {label} Worker
        {running ? (
          <Badge variant="success" className="ml-1 text-[9px]">
            LIVE
          </Badge>
        ) : (
          <Badge variant="muted" className="ml-1 text-[9px]">
            IDLE
          </Badge>
        )}
      </div>

      <div className={running ? "[&>div]:glow-card-live" : ""}>
        <WorkerControls
          title={`${label} Worker`}
          status={status}
          onStart={(p) => start.mutate(p)}
          onStop={() => stop.mutate()}
          isStarting={start.isPending}
          isStopping={stop.isPending}
          showLocation
        />
      </div>

      <Card>
        <CardContent className="flex items-center gap-2 p-4">
          <Button
            type="button"
            size="sm"
            variant={previewSource === "rtsp" ? "default" : "secondary"}
            onClick={() => setPreviewSource("rtsp")}
          >
            RTSP Camera
          </Button>
          <Button
            type="button"
            size="sm"
            variant={previewSource === "webcam" ? "default" : "secondary"}
            onClick={() => setPreviewSource("webcam")}
          >
            Webcam
          </Button>
        </CardContent>
      </Card>

      {previewSource === "webcam" ? (
        <ArmedWebcamPreview module={module} title={`${label} Live Preview`} label={label} />
      ) : (
        <WorkerFramePreview module={module} title={`${label} Live Preview`} />
      )}
    </div>
  );
}

interface ArmedPredictResponse {
  knife?: boolean;
  weapon?: boolean;
  image_b64?: string | null;
  detections?: unknown[];
}

function ArmedWebcamPreview({
  module,
  title,
  label,
}: {
  module: ArmedModule;
  title: string;
  label: string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const inflightRef = useRef(false);

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [detected, setDetected] = useState(false);

  const loadDevices = useCallback(async () => {
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      const cams = list.filter((d) => d.kind === "videoinput");
      setDevices(cams);
      setSelected((prev) => prev || cams[0]?.deviceId || "");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return null;
    if (!canvasRef.current) canvasRef.current = document.createElement("canvas");
    const canvas = canvasRef.current;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, w, h);
    return await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
  }, []);

  const tick = useCallback(async () => {
    if (inflightRef.current) return;
    inflightRef.current = true;
    try {
      const blob = await captureFrame();
      if (!blob) return;
      const form = new FormData();
      form.set("file", blob, `${module}-webcam.jpg`);
      form.set("camera_id", module === "knife" ? "KNIFE_WEBCAM" : "WEAPON_WEBCAM");
      const path = module === "knife" ? "/knife/predict/image" : "/weapon/predict/image";
      const data = await apiPostForm<ArmedPredictResponse>(path, form);
      setResultImage(data.image_b64 ? `data:image/jpeg;base64,${data.image_b64}` : null);
      setDetected(module === "knife" ? Boolean(data.knife) : Boolean(data.weapon));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      inflightRef.current = false;
    }
  }, [captureFrame, module]);

  const start = useCallback(async () => {
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ video: true, audio: false }).then((s) => {
        s.getTracks().forEach((t) => t.stop());
      });
      await loadDevices();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: selected ? { deviceId: { exact: selected } } : true,
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setRunning(true);
      if (timerRef.current) window.clearInterval(timerRef.current);
      tick();
      timerRef.current = window.setInterval(tick, 1500);
    } catch (e) {
      setError((e as Error).message || "Failed to open webcam");
      setRunning(false);
    }
  }, [loadDevices, selected, tick]);

  const stop = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    inflightRef.current = false;
    setRunning(false);
    setResultImage(null);
    setDetected(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const statusText = !running ? "OFFLINE" : detected ? `${label.toUpperCase()} DETECTED` : "CLEAR";
  const statusDot = !running ? "bg-muted-foreground" : detected ? "bg-destructive" : "bg-emerald-500";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 border-b border-border/60 py-4">
        <CardTitle className="text-sm">{title} - Webcam</CardTitle>
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="h-8 rounded border border-input bg-background px-2 text-xs"
          >
            {devices.length === 0 ? <option value="">No devices</option> : null}
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Camera ${d.deviceId.slice(0, 4)}`}
              </option>
            ))}
          </select>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={loadDevices}
            title="Refresh devices"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          {!running ? (
            <Button type="button" size="sm" className="h-8" onClick={start}>
              <Play className="h-3.5 w-3.5" />
              Start
            </Button>
          ) : (
            <Button type="button" size="sm" variant="destructive" className="h-8" onClick={stop}>
              <Square className="h-3.5 w-3.5" />
              Stop
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">{label} Webcam Preview</span>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border/60 px-2.5 py-1 text-[11px] font-medium">
            <span className={`h-2 w-2 rounded-full ${statusDot}`} />
            {statusText}
          </div>
        </div>
        <div className="relative aspect-video w-full overflow-hidden rounded-md border border-border/60 bg-black">
          <video
            ref={videoRef}
            className={`h-full w-full object-contain ${resultImage ? "invisible" : ""}`}
            autoPlay
            muted
            playsInline
          />
          {resultImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resultImage}
              alt={`${module} webcam preview`}
              className="absolute inset-0 h-full w-full object-contain"
            />
          ) : null}
          {running && detected ? (
            <div className="absolute left-3 top-3 rounded bg-destructive/90 px-2 py-1 text-[11px] font-semibold text-destructive-foreground">
              {label} detected
            </div>
          ) : null}
          {error ? (
            <div className="absolute bottom-3 left-3 right-3 rounded bg-destructive/90 px-3 py-2 text-xs text-destructive-foreground">
              {error}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition ${
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-border/60 bg-background text-muted-foreground hover:border-primary/50"
      }`}
    >
      {children}
    </button>
  );
}

function ArmedEventCard({
  event,
}: {
  event: DetectionEvent & { _module: ArmedModule };
}) {
  const label = event._module === "knife" ? "Knife" : "Firearm";
  return (
    <div className="relative">
      <Badge
        variant="destructive"
        className="absolute right-2 top-2 z-10 gap-1 text-[9px]"
      >
        {event._module === "knife" ? (
          <Swords className="h-2.5 w-2.5" />
        ) : (
          <Crosshair className="h-2.5 w-2.5" />
        )}
        {label}
      </Badge>
      <EventCard
        title={label}
        snapshotUrl={event.snapshot_url || undefined}
        cameraId={event.camera_id}
        cameraLocation={event.camera_location || undefined}
        eventTime={event.event_time}
        confidence={event.confidence ?? undefined}
        alertLevel={event.alert_level || undefined}
        description={event.description || undefined}
      />
    </div>
  );
}
