"use client";

import { useState } from "react";
import { AlertOctagon, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EventCard } from "@/components/common/EventCard";
import { useAccidents } from "@/lib/hooks/useEvents";

export function AccidentFeed() {
  const [cameraFilter, setCameraFilter] = useState("");
  const [applied, setApplied] = useState<string | undefined>(undefined);
  const { data = [], refetch, isFetching } = useAccidents({ camera_id: applied });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 border-b border-border/60 py-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertOctagon className="h-4 w-4 text-destructive" />
          Accident Events
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
              setApplied(cameraFilter || undefined);
              refetch();
            }}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-5">
        {data.length === 0 ? (
          <div className="flex h-28 items-center justify-center rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
            No accident events recorded.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.map((a) => (
              <EventCard
                key={String(a.id)}
                title="Accident"
                snapshotUrl={a.snapshot_path || undefined}
                cameraId={a.camera_id || undefined}
                eventTime={a.event_time}
                confidence={a.confidence ?? undefined}
                clipUrl={a.clip_path || undefined}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
