"use client";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMissingAlerts } from "@/lib/hooks/useEvents";
import { formatDateTime, formatDurationSeconds } from "@/lib/utils";

export function MissingAlertsPanel() {
  const { data, isLoading } = useMissingAlerts();
  const alerts = data?.alerts ?? [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="border-b border-destructive/20 bg-destructive/10 py-3">
        <CardTitle className="flex items-center gap-2 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" />
          Missing Vehicles
          <Badge variant="destructive" className="ml-2">{alerts.length}</Badge>
          {typeof data?.threshold_s === "number" ? (
            <span className="ml-auto text-[10px] font-mono uppercase text-destructive/80">
              {`> ${formatDurationSeconds(data.threshold_s)}`}
            </span>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-3">
        {isLoading && alerts.length === 0 ? (
          <div className="py-6 text-center text-xs text-muted-foreground">Loading…</div>
        ) : alerts.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-xs text-muted-foreground">
            No missing vehicles.
          </div>
        ) : (
          <ul className="space-y-2">
            {alerts.map((a, i) => (
              <li
                key={`${a.plate_number}-${i}`}
                className="flex items-center justify-between gap-3 rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm font-bold text-destructive">
                    {a.plate_number}
                  </div>
                  <div className="truncate text-[10px] text-muted-foreground">
                    Entered {formatDateTime(a.entry_time)}
                  </div>
                </div>
                <Badge variant="destructive" className="shrink-0 font-mono">
                  {formatDurationSeconds(a.missing_for_s)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
