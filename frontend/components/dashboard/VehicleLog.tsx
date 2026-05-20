"use client";

import { useState } from "react";
import { Car, Filter, RotateCcw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useVehicleEvents } from "@/lib/hooks/useEvents";
import { formatDateTime } from "@/lib/utils";

export function VehicleLog() {
  const [plate, setPlate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [applied, setApplied] = useState<{
    plate?: string;
    start_time?: string;
    end_time?: string;
  }>({});

  const { data, isLoading } = useVehicleEvents(applied);
  const events = data?.events ?? [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 border-b border-border/60 py-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Car className="h-4 w-4" />
          Vehicle Log
          <Badge variant="muted" className="ml-2 font-mono">
            {events.length}
          </Badge>
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={plate}
              onChange={(e) => setPlate(e.target.value)}
              placeholder="Plate…"
              className="h-8 w-36 pl-8 font-mono text-xs"
            />
          </div>
          <Input
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="h-8 w-44 font-mono text-[11px]"
          />
          <Input
            type="datetime-local"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            className="h-8 w-44 font-mono text-[11px]"
          />
          <Button
            size="sm"
            variant="secondary"
            className="h-8"
            onClick={() =>
              setApplied({
                plate: plate || undefined,
                start_time: startTime ? new Date(startTime).toISOString() : undefined,
                end_time: endTime ? new Date(endTime).toISOString() : undefined,
              })
            }
          >
            <Filter className="h-3.5 w-3.5" />
            Filter
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={() => {
              setPlate("");
              setStartTime("");
              setEndTime("");
              setApplied({});
            }}
            title="Reset filters"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="min-h-[280px] flex-1 overflow-auto p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Plate Number</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Entry Time</TableHead>
              <TableHead>Exit Time</TableHead>
              <TableHead>Cameras</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-xs text-muted-foreground">
                  Loading vehicle log…
                </TableCell>
              </TableRow>
            ) : events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-xs text-muted-foreground">
                  No vehicles recorded yet.
                </TableCell>
              </TableRow>
            ) : (
              events.map((e, i) => (
                <TableRow key={`${e.plate_number}-${i}`}>
                  <TableCell className="font-mono text-sm font-semibold">
                    {e.plate_number}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        e.alert_flag
                          ? "destructive"
                          : String(e.status).toUpperCase() === "IN"
                          ? "warning"
                          : "success"
                      }
                    >
                      {e.alert_flag ? "ALERT" : String(e.status).toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {formatDateTime(e.entry_time)}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {formatDateTime(e.exit_time)}
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">
                    {e.entry_camera_id || "-"} → {e.exit_camera_id || "-"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
