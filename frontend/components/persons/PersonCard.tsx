"use client";

import { User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { PersonRecord } from "@/lib/types";

interface PersonCardProps {
  person: PersonRecord;
  selected?: boolean;
  onClick?: () => void;
  compact?: boolean;
}

export function PersonCard({ person, selected, onClick, compact }: PersonCardProps) {
  const thumb = person.image_b64 ? `data:image/jpeg;base64,${person.image_b64}` : null;
  const tags = person.tags || [];

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group relative flex w-full items-start gap-3 overflow-hidden rounded-lg border bg-card p-3 text-left transition hover:border-primary/60 hover:bg-accent/40 ${
        selected ? "border-primary ring-2 ring-primary/40" : "border-border/60"
      }`}
    >
      <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-md border border-border/60 bg-muted">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={person.name ?? "person"} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <User className="h-6 w-6" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-sm font-semibold">{person.name || "Unnamed"}</span>
          {person.age ? (
            <span className="font-mono text-[10px] text-muted-foreground">age {person.age}</span>
          ) : null}
        </div>
        {!compact && person.phone ? (
          <div className="truncate text-xs text-muted-foreground">{person.phone}</div>
        ) : null}
        {!compact && person.address ? (
          <div className="truncate text-xs text-muted-foreground">{person.address}</div>
        ) : null}
        {tags.length ? (
          <div className="flex flex-wrap gap-1 pt-1">
            {tags.slice(0, 6).map((t) => (
              <Badge key={t} variant={t.toLowerCase() === "suspect" ? "destructive" : "muted"} className="text-[9px]">
                {t}
              </Badge>
            ))}
            {tags.length > 6 ? (
              <span className="text-[10px] text-muted-foreground">+{tags.length - 6}</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </button>
  );
}
