"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Globe, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPostForm } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";
import type {
  RecognitionMatch,
  RecognitionPlate,
  RecognizeRtspResponse,
} from "@/lib/types";
import { FaceBoxOverlay, PlateBoxOverlay } from "@/components/common/DetectionOverlay";

interface RtspPanelProps {
  onFrame?: (data: RecognizeRtspResponse) => void;
  defaultUrl?: string;
  pollMs?: number;
  location?: string;
  cameraId?: string;
  eventType?: string;
}

interface RecognizeResponse {
  matches: RecognitionMatch[];
  plates: RecognitionPlate[];
  message?: string;
}

function base64ToBlob(base64: string, type = "image/jpeg"): Blob {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type });
}

export function RtspPanel({
  onFrame,
  defaultUrl = "rtsp://admin:fcse1234@10.1.139.235:554/Streaming/Channels/101",
  pollMs = 500,
  location,
  cameraId,
  eventType,
}: RtspPanelProps) {
  const [url, setUrl] = useState(defaultUrl);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<RecognitionMatch[]>([]);
  const [plates, setPlates] = useState<RecognitionPlate[]>([]);
  const [naturalDims, setNaturalDims] = useState<{ w: number; h: number } | null>(null);

  const imgRef = useRef<HTMLImageElement | null>(null);
  const lastTsRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const runningRef = useRef(false);
  const inflightRef = useRef(false);
  const detectInflightRef = useRef(false);

  const detectFrame = useCallback(
    async (data: RecognizeRtspResponse) => {
      if (!data.image_b64 || detectInflightRef.current) return;
      detectInflightRef.current = true;
      try {
        const detectForm = new FormData();
        detectForm.set("file", base64ToBlob(data.image_b64), "rtsp-frame.jpg");
        if (location) detectForm.set("location", location);
        if (cameraId) detectForm.set("camera_id", cameraId);
        if (eventType) detectForm.set("event_type", eventType);
        detectForm.set("enable_face", "true");

        const detectData = await apiPostForm<RecognizeResponse>(
          endpoints.recognizePerson,
          detectForm
        );
        if (!runningRef.current) return;
        setMatches(detectData.matches ?? []);
        setPlates(detectData.plates ?? []);
        onFrame?.({
          ...data,
          matches: detectData.matches ?? [],
          plates: detectData.plates ?? [],
        });
      } catch (e) {
        if (runningRef.current) setError((e as Error).message);
      } finally {
        detectInflightRef.current = false;
      }
    },
    [location, cameraId, eventType, onFrame]
  );

  const tick = useCallback(async () => {
    if (!runningRef.current || inflightRef.current) return;
    inflightRef.current = true;
    const form = new FormData();
    form.set("rtsp_url", url);
    if (location) form.set("location", location);
    if (cameraId) form.set("camera_id", cameraId);
    if (eventType) form.set("event_type", eventType);
    if (lastTsRef.current !== null) form.set("last_ts", String(lastTsRef.current));
    try {
      const data = await apiPostForm<RecognizeRtspResponse>(endpoints.recognizeRtsp, form);
      if (data.frame_ts) lastTsRef.current = data.frame_ts;
      if (data.image_b64 && imgRef.current) {
        imgRef.current.src = `data:image/jpeg;base64,${data.image_b64}`;
        void detectFrame(data);
      } else {
        setMatches([]);
        setPlates([]);
        onFrame?.(data);
      }
      if (data.error && !data.image_b64) setError(data.error);
      else setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      inflightRef.current = false;
    }
  }, [url, location, cameraId, eventType, onFrame, detectFrame]);

  const start = useCallback(() => {
    setRunning(true);
    runningRef.current = true;
    setError(null);
    if (timerRef.current) window.clearInterval(timerRef.current);
    tick();
    timerRef.current = window.setInterval(tick, pollMs);
  }, [tick, pollMs]);

  const stop = useCallback(() => {
    setRunning(false);
    runningRef.current = false;
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    inflightRef.current = false;
    detectInflightRef.current = false;
    setMatches([]);
    setPlates([]);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, []);

  const onImgLoad = () => {
    const img = imgRef.current;
    if (!img) return;
    if (img.naturalWidth && img.naturalHeight) {
      setNaturalDims((prev) =>
        prev &&
        prev.w === img.naturalWidth &&
        prev.h === img.naturalHeight
          ? prev
          : { w: img.naturalWidth, h: img.naturalHeight }
      );
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border/60 bg-card/60">
      <div className="flex h-11 items-center justify-between border-b border-border/60 bg-background/40 px-4">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Entry Camera (RTSP)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="h-7 w-56 font-mono text-[10px]"
            spellCheck={false}
            disabled={running}
          />
          {!running ? (
            <Button size="sm" className="h-7" onClick={start}>
              <Play className="h-3.5 w-3.5" />
              Connect
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
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          alt="RTSP preview"
          className="h-full w-full object-contain"
          onLoad={onImgLoad}
        />

        {naturalDims ? (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${naturalDims.w} ${naturalDims.h}`}
            preserveAspectRatio="xMidYMid meet"
            aria-hidden
          >
            {matches.map((m, idx) => (
              <FaceBoxOverlay
                key={`${m.person_id ?? "unk"}-${idx}`}
                match={m}
                canvasW={naturalDims.w}
                canvasH={naturalDims.h}
              />
            ))}
            {plates.map((p, idx) => (
              <PlateBoxOverlay
                key={`${p.text}-${idx}`}
                plate={p}
                canvasW={naturalDims.w}
                canvasH={naturalDims.h}
              />
            ))}
          </svg>
        ) : null}

        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 text-[10px] font-semibold uppercase text-white">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              running ? "bg-primary animate-pulse" : "bg-muted-foreground"
            }`}
          />
          {running ? "Network Stream" : "Disconnected"}
        </div>

        {running && matches.length === 0 && plates.length === 0 ? (
          <div className="absolute right-3 top-3 rounded bg-black/60 px-2 py-1 font-mono text-[10px] text-white">
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
