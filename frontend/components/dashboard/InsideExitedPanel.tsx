"use client";

import { ParkingSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useVehicleEvents } from "@/lib/hooks/useEvents";
import { formatDateTime } from "@/lib/utils";
import type { VehicleEvent } from "@/lib/types";

function Row({ e }: { e: VehicleEvent }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background/40 px-3 py-2">
      <div className="min-w-0">
        <div className="font-mono text-xs font-semibold">{e.plate_number}</div>
        <div className="truncate text-[10px] text-muted-foreground">
          {e.status === "OUT"
            ? `Exited ${formatDateTime(e.exit_time)}`
            : `Entered ${formatDateTime(e.entry_time)}`}
        </div>
      </div>
      <Badge variant={e.status === "OUT" ? "success" : "warning"}>
        {String(e.status).toUpperCase()}
      </Badge>
    </li>
  );
}

export function InsideExitedPanel() {
  const { data } = useVehicleEvents();
  const inside = data?.inside ?? [];
  const exited = data?.exited ?? [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="border-b border-border/60 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ParkingSquare className="h-4 w-4 text-primary" />
          Inside & Exited
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-4 overflow-y-auto p-3">
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Currently Inside
            </h4>
            <Badge variant="muted" className="font-mono">{inside.length}</Badge>
          </div>
          {inside.length === 0 ? (
            <p className="text-xs text-muted-foreground">None.</p>
          ) : (
            <ul className="space-y-2">
              {inside.slice(0, 20).map((e, i) => <Row key={`in-${i}`} e={e} />)}
            </ul>
          )}
        </section>
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Recently Exited
            </h4>
            <Badge variant="muted" className="font-mono">{exited.length}</Badge>
          </div>
          {exited.length === 0 ? (
            <p className="text-xs text-muted-foreground">None yet.</p>
          ) : (
            <ul className="space-y-2">
              {exited.slice(0, 20).map((e, i) => <Row key={`out-${i}`} e={e} />)}
            </ul>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
