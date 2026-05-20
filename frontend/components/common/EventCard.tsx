import { Camera, Clock, ExternalLink, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatDateTime, formatRelativeTime } from "@/lib/utils";

interface EventCardProps {
  title: string;
  snapshotUrl?: string | null;
  cameraId?: string | null;
  cameraLocation?: string | null;
  eventTime?: string | null;
  confidence?: number | null;
  alertLevel?: string | null;
  description?: string | null;
  clipUrl?: string | null;
}

export function EventCard({
  title,
  snapshotUrl,
  cameraId,
  cameraLocation,
  eventTime,
  confidence,
  alertLevel,
  description,
  clipUrl,
}: EventCardProps) {
  const conf = typeof confidence === "number" ? `${(confidence * 100).toFixed(0)}%` : null;

  return (
    <div className="group overflow-hidden rounded-lg border border-border/60 bg-card/60 transition hover:border-primary/40">
      <div className="relative aspect-video bg-black/60">
        {snapshotUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={snapshotUrl}
            alt={title}
            className="h-full w-full object-cover transition group-hover:scale-[1.01]"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            No snapshot
          </div>
        )}
        <div className="absolute left-2 top-2 flex items-center gap-1.5">
          <Badge variant="destructive" className="uppercase">
            {title}
          </Badge>
          {alertLevel ? (
            <Badge variant="warning" className="uppercase">
              {alertLevel}
            </Badge>
          ) : null}
        </div>
        {conf ? (
          <div className="absolute right-2 top-2 rounded bg-black/70 px-2 py-0.5 font-mono text-[10px] text-white">
            {conf}
          </div>
        ) : null}
      </div>
      <div className="space-y-1.5 p-3">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Camera className="h-3.5 w-3.5" />
          <span className="truncate font-mono">{cameraId || "unknown camera"}</span>
        </div>
        {cameraLocation ? (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3.5 w-3.5" />
            <span className="truncate">{cameraLocation}</span>
          </div>
        ) : null}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          <span title={formatDateTime(eventTime)}>{formatRelativeTime(eventTime)}</span>
        </div>
        {description ? (
          <p className="line-clamp-2 text-xs text-muted-foreground/90">{description}</p>
        ) : null}
        {clipUrl ? (
          <a
            href={clipUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Open clip
          </a>
        ) : null}
      </div>
    </div>
  );
}
