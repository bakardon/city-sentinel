"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Flame, Play, RefreshCw, Square } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { WorkerControls } from "@/components/workers/WorkerControls";
import { WorkerFramePreview } from "@/components/workers/WorkerFramePreview";
import { EventCard } from "@/components/common/EventCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiPostForm } from "@/lib/api";
import { useDetectionWorkerStatus } from "@/lib/hooks/useWorkerStatus";
import { useDetectionWorkerMutations } from "@/lib/hooks/useWorkerMutations";
import { useDetectionEvents } from "@/lib/hooks/useEvents";
import type { DetectionModule } from "@/lib/endpoints";

interface DetectionModulePageProps {
  module: DetectionModule;
  title: string;
  description: string;
  alertLabel: string;
}

export function DetectionModulePage({ module, title, description, alertLabel }: DetectionModulePageProps) {
  const { data: status } = useDetectionWorkerStatus(module);
  const { start, stop } = useDetectionWorkerMutations(module);
  const [previewSource, setPreviewSource] = useState<"rtsp" | "webcam">("rtsp");

  const [cameraFilter, setCameraFilter] = useState("");
  const [appliedCamera, setAppliedCamera] = useState<string | undefined>(undefined);
  const { data: events = [], refetch, isFetching } = useDetectionEvents(module, {
    camera_id: appliedCamera,
  });

  return (
    <>
      <PageHeader title={title} description={description} />

      <WorkerControls
        title={`${title} Worker`}
        status={status}
        onStart={(p) => start.mutate(p)}
        onStop={() => stop.mutate()}
        isStarting={start.isPending}
        isStopping={stop.isPending}
        showLocation
      />

      {module === "fire" ? (
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
      ) : null}

      {module === "fire" && previewSource === "webcam" ? (
        <FireWebcamPreview title={`${title} Live Preview`} />
      ) : (
        <WorkerFramePreview module={module} title={`${title} Live Preview`} />
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 border-b border-border/60 py-4">
          <CardTitle className="text-sm">Recent {alertLabel} Events</CardTitle>
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
          {events.length === 0 ? (
            <div className="flex h-28 items-center justify-center rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
              No {alertLabel.toLowerCase()} events recorded.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {events.map((e) => (
                <EventCard
                  key={String(e.id)}
                  title={alertLabel}
                  snapshotUrl={e.snapshot_url || undefined}
                  cameraId={e.camera_id}
                  cameraLocation={e.camera_location || undefined}
                  eventTime={e.event_time}
                  confidence={e.confidence ?? undefined}
                  alertLevel={e.alert_level || undefined}
                  description={e.description || undefined}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

interface FirePredictResponse {
  fire?: boolean;
  image_b64?: string | null;
  detections?: unknown[];
}

function FireWebcamPreview({ title }: { title: string }) {
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
  const [fireDetected, setFireDetected] = useState(false);

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
      form.set("file", blob, "fire-webcam.jpg");
      form.set("camera_id", "FIRE_WEBCAM");
      const data = await apiPostForm<FirePredictResponse>("/fire/predict/image", form);
      setResultImage(data.image_b64 ? `data:image/jpeg;base64,${data.image_b64}` : null);
      setFireDetected(Boolean(data.fire));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      inflightRef.current = false;
    }
  }, [captureFrame]);

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
    setFireDetected(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

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
            <span className="text-sm font-semibold">Webcam Fire Preview</span>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border/60 px-2.5 py-1 text-[11px] font-medium">
            <span
              className={`h-2 w-2 rounded-full ${
                !running ? "bg-muted-foreground" : fireDetected ? "bg-destructive" : "bg-emerald-500"
              }`}
            />
            {!running ? "OFFLINE" : fireDetected ? "FIRE DETECTED" : "CLEAR"}
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
              alt="fire webcam preview"
              className="absolute inset-0 h-full w-full object-contain"
            />
          ) : null}
          {running && fireDetected ? (
            <div className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded bg-destructive/90 px-2 py-1 text-[11px] font-semibold text-destructive-foreground">
              <Flame className="h-3.5 w-3.5" />
              Fire detected
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
