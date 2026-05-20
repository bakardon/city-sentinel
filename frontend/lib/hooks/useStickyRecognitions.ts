"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RecognitionMatch } from "@/lib/types";

export interface StickyRecognition extends RecognitionMatch {
  uid: string;
  first_seen: number;
  last_seen: number;
  sightings: number;
  best_score: number;
}

interface StickyStats {
  total_unique: number;
  frames_with_face: number;
  frames_empty: number;
  last_face_ts: number | null;
  last_match_ts: number | null;
}

export interface UseStickyRecognitionsResult {
  list: StickyRecognition[];
  stats: StickyStats;
  add: (matches: RecognitionMatch[] | undefined) => void;
  clear: () => void;
}

export function useStickyRecognitions(
  expiryMs: number = 20000
): UseStickyRecognitionsResult {
  const [list, setList] = useState<StickyRecognition[]>([]);
  const [stats, setStats] = useState<StickyStats>({
    total_unique: 0,
    frames_with_face: 0,
    frames_empty: 0,
    last_face_ts: null,
    last_match_ts: null,
  });
  const knownUidsRef = useRef<Set<string>>(new Set());

  const prune = useCallback(() => {
    const cutoff = Date.now() - expiryMs;
    setList((prev) => prev.filter((r) => r.last_seen >= cutoff));
  }, [expiryMs]);

  useEffect(() => {
    const id = window.setInterval(prune, 2000);
    return () => window.clearInterval(id);
  }, [prune]);

  const add = useCallback(
    (matches: RecognitionMatch[] | undefined) => {
      const now = Date.now();
      const incoming = matches ?? [];

      setStats((s) => ({
        total_unique: s.total_unique,
        frames_with_face: s.frames_with_face + (incoming.length > 0 ? 1 : 0),
        frames_empty: s.frames_empty + (incoming.length === 0 ? 1 : 0),
        last_face_ts: incoming.length > 0 ? now : s.last_face_ts,
        last_match_ts:
          incoming.some((m) => m.person_id) ? now : s.last_match_ts,
      }));

      if (incoming.length === 0) return;

      setList((prev) => {
        const cutoff = now - expiryMs;
        const keep = prev.filter((r) => r.last_seen >= cutoff);
        const byUid = new Map(keep.map((r) => [r.uid, r]));
        let addedUniques = 0;

        for (const m of incoming) {
          const score = typeof m.similarity === "number" ? m.similarity : 0;
          const uid = makeUid(m);
          const existing = byUid.get(uid);
          if (existing) {
            byUid.set(uid, {
              ...existing,
              ...m,
              uid,
              last_seen: now,
              sightings: existing.sightings + 1,
              best_score: Math.max(existing.best_score, score),
              image_b64: m.image_b64 ?? existing.image_b64 ?? null,
            });
          } else {
            byUid.set(uid, {
              ...m,
              uid,
              first_seen: now,
              last_seen: now,
              sightings: 1,
              best_score: score,
            });
            if (!knownUidsRef.current.has(uid)) {
              knownUidsRef.current.add(uid);
              addedUniques += 1;
            }
          }
        }

        if (addedUniques > 0) {
          setStats((s) => ({ ...s, total_unique: s.total_unique + addedUniques }));
        }

        return Array.from(byUid.values()).sort((a, b) => b.last_seen - a.last_seen);
      });
    },
    [expiryMs]
  );

  const clear = useCallback(() => {
    setList([]);
    knownUidsRef.current = new Set();
    setStats({
      total_unique: 0,
      frames_with_face: 0,
      frames_empty: 0,
      last_face_ts: null,
      last_match_ts: null,
    });
  }, []);

  return { list, stats, add, clear };
}

function makeUid(m: RecognitionMatch): string {
  if (m.person_id) return `p:${m.person_id}`;
  const box = m.box;
  if (box) {
    const cx = Math.round((box.x1 + box.x2) / 2 / 40);
    const cy = Math.round((box.y1 + box.y2) / 2 / 40);
    return `u:${cx}:${cy}`;
  }
  return `u:${m.name ?? "anon"}`;
}
