"use client";

import { Eye, ScanFace, User2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/utils";
import type { StickyRecognition } from "@/lib/hooks/useStickyRecognitions";

interface RecognitionFeedProps {
  matches: StickyRecognition[];
  expiryMs?: number;
}

export function RecognitionFeed({ matches, expiryMs = 20000 }: RecognitionFeedProps) {
  if (!matches.length) {
    return (
      <div className="flex h-32 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
        <ScanFace className="h-6 w-6" />
        <div>No faces detected in the recent window.</div>
        <div className="text-[10px]">
          Connect the RTSP camera and stand clearly in frame.
        </div>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {matches.map((m) => {
        const ageMs = Date.now() - m.last_seen;
        const fading = ageMs > expiryMs * 0.5;
        const isKnown = !!m.person_id;
        const scorePct = (m.best_score ?? 0) * 100;
        return (
          <div
            key={m.uid}
            className={`overflow-hidden rounded-lg border bg-card/70 transition-opacity ${
              isKnown ? "border-primary/50" : "border-warning/40"
            } ${fading ? "opacity-60" : "opacity-100"}`}
          >
            <div className="relative aspect-square bg-black/60">
              {m.image_b64 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`data:image/jpeg;base64,${m.image_b64}`}
                  alt={m.name || "face"}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <User2 className="h-10 w-10" />
                </div>
              )}
              <div className="absolute right-2 top-2 rounded bg-black/70 px-2 py-0.5 font-mono text-[10px] text-white">
                {scorePct.toFixed(0)}%
              </div>
              {m.sightings > 1 ? (
                <div className="absolute left-2 top-2 flex items-center gap-1 rounded bg-primary/80 px-1.5 py-0.5 font-mono text-[10px] text-primary-foreground">
                  <Eye className="h-2.5 w-2.5" />
                  {m.sightings}
                </div>
              ) : null}
            </div>
            <div className="space-y-1 p-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-sm font-semibold">
                  {m.name || (isKnown ? "Unnamed" : "Unknown")}
                </div>
                {m.tag_status ? (
                  <Badge variant="warning" className="uppercase">
                    {m.tag_status}
                  </Badge>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-1">
                {(m.tags || []).slice(0, 3).map((t) => (
                  <Badge key={t} variant="muted" className="text-[10px]">
                    {t}
                  </Badge>
                ))}
              </div>
              <div className="text-[10px] text-muted-foreground">
                Last seen {formatRelativeTime(new Date(m.last_seen).toISOString())}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
