"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Play, Square, RefreshCw, ScanFace } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiPostForm } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";
import type { RecognitionMatch, RecognitionPlate } from "@/lib/types";
import { FaceBoxOverlay, PlateBoxOverlay } from "@/components/common/DetectionOverlay";

interface RecognizeResponse {
  matches: RecognitionMatch[];
  plates: RecognitionPlate[];
  message?: string;
}

interface WebcamPanelProps {
  title?: string;
  /** Called every time the backend returns a recognition result. */
  onFrame?: (data: RecognizeResponse) => void;
  /** How often to send a frame for recognition (ms). */
  pollMs?: number;
  /** Optional location tag to send with each frame. */
  location?: string;
  /** Optional camera id tag to send with each frame. */
  cameraId?: string;
  /** Optional vehicle flow event type to log with plate detections. */
  eventType?: string;
  /** If false, the webcam will only show the feed and skip recognition. */
  recognize?: boolean;
}

export function WebcamPanel({
  title = "Exit Camera (Webcam)",
  onFrame,
  pollMs = 1500,
  location = "Exit",
  cameraId = "webcam",
  eventType,
  recognize = true,
}: WebcamPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const inflightRef = useRef(false);
  const runningRef = useRef(false);

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<RecognitionMatch[]>([]);
  const [plates, setPlates] = useState<RecognitionPlate[]>([]);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);

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
    setDims((prev) => (prev && prev.w === w && prev.h === h ? prev : { w, h }));
    return await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.82)
    );
  }, []);

  const tick = useCallback(async () => {
    if (!runningRef.current) return;
    if (inflightRef.current) return;
    inflightRef.current = true;
    try {
      const blob = await captureFrame();
      if (!blob) return;
      const form = new FormData();
      form.set("file", blob, "frame.jpg");
      form.set("location", location);
      form.set("camera_id", cameraId);
      if (eventType) form.set("event_type", eventType);
      const data = await apiPostForm<RecognizeResponse>(endpoints.recognizePerson, form);
      setMatches(data.matches ?? []);
      setPlates(data.plates ?? []);
      setError(null);
      onFrame?.(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      inflightRef.current = false;
    }
  }, [captureFrame, location, cameraId, eventType, onFrame]);

  const startRecognitionLoop = useCallback(() => {
    if (!recognize) return;
    if (timerRef.current) window.clearInterval(timerRef.current);
    tick();
    timerRef.current = window.setInterval(tick, pollMs);
  }, [recognize, tick, pollMs]);

  const stopRecognitionLoop = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    inflightRef.current = false;
  }, []);

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
      runningRef.current = true;
      startRecognitionLoop();
    } catch (e) {
      setError((e as Error).message || "Failed to open webcam");
      setRunning(false);
      runningRef.current = false;
    }
  }, [selected, loadDevices, startRecognitionLoop]);

  const stop = useCallback(() => {
    stopRecognitionLoop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setRunning(false);
    runningRef.current = false;
    setMatches([]);
    setPlates([]);
  }, [stopRecognitionLoop]);

  useEffect(() => {
    return () => {
      stopRecognitionLoop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [stopRecognitionLoop]);

  const onLoadedMetadata = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.videoWidth && v.videoHeight) {
      setDims({ w: v.videoWidth, h: v.videoHeight });
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border/60 bg-card/60">
      <div className="flex h-11 items-center justify-between border-b border-border/60 bg-background/40 px-4">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-warning" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="h-7 rounded border border-input bg-background px-2 text-xs"
          >
            {devices.length === 0 ? <option value="">No devices</option> : null}
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Camera ${d.deviceId.slice(0, 4)}`}
              </option>
            ))}
          </select>
          <Button size="icon" variant="ghost" onClick={loadDevices} className="h-7 w-7" title="Refresh devices">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          {!running ? (
            <Button size="sm" className="h-7" onClick={start}>
              <Play className="h-3.5 w-3.5" />
              Start
            </Button>
          ) : (
            <Button size="sm" variant="destructive" className="h-7" onClick={stop}>
              <Square className="h-3.5 w-3.5" />
              Stop
            </Button>
          )}
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden bg-black">
        <video
          ref={videoRef}
          className="h-full w-full object-contain"
          autoPlay
          muted
          playsInline
          onLoadedMetadata={onLoadedMetadata}
        />

        {dims && running ? (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${dims.w} ${dims.h}`}
            preserveAspectRatio="xMidYMid meet"
            aria-hidden
          >
            {matches.map((m, idx) => (
              <FaceBoxOverlay
                key={`${m.person_id ?? "unk"}-${idx}`}
                match={m}
                canvasW={dims.w}
                canvasH={dims.h}
              />
            ))}
            {plates.map((p, idx) => (
              <PlateBoxOverlay
                key={`${p.text}-${idx}`}
                plate={p}
                canvasW={dims.w}
                canvasH={dims.h}
              />
            ))}
          </svg>
        ) : null}

        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 text-[10px] font-semibold uppercase text-white">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              running ? "bg-destructive animate-pulse" : "bg-muted-foreground"
            }`}
          />
          {running ? "Live Feed" : "Offline"}
        </div>

        {running && recognize && matches.length === 0 && plates.length === 0 ? (
          <div className="absolute right-3 top-3 flex items-center gap-1 rounded bg-black/60 px-2 py-1 font-mono text-[10px] text-white">
            <ScanFace className="h-3 w-3" />
            scanning…
          </div>
        ) : null}

        {error ? (
          <div className="absolute bottom-3 left-3 right-3 rounded bg-destructive/90 px-3 py-2 text-xs text-destructive-foreground">
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}
