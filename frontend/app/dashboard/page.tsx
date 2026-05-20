"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { WebcamPanel } from "@/components/common/WebcamPanel";
import { RtspPanel } from "@/components/common/RtspPanel";
import { RecognitionFeed } from "@/components/common/RecognitionFeed";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScanSearch, Activity, Trash2 } from "lucide-react";
import { VehicleLog } from "@/components/dashboard/VehicleLog";
import { MissingAlertsPanel } from "@/components/dashboard/MissingAlertsPanel";
import { InsideExitedPanel } from "@/components/dashboard/InsideExitedPanel";
import { AccidentFeed } from "@/components/dashboard/AccidentFeed";
import { AccidentWorkerCard } from "@/components/dashboard/AccidentWorkerCard";
import { useStickyRecognitions } from "@/lib/hooks/useStickyRecognitions";
import { formatRelativeTime } from "@/lib/utils";

const RECOGNITION_EXPIRY_MS = 20000;

export default function DashboardPage() {
  const { list, stats, add, clear } = useStickyRecognitions(RECOGNITION_EXPIRY_MS);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live cameras, vehicle traffic, face recognition, and accident monitoring."
      />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="h-[420px]">
          <WebcamPanel
            onFrame={(d) => add(d.matches)}
            location="Exit"
            cameraId="exit-webcam"
            eventType="exit"
          />
        </div>
        <div className="h-[420px]">
          <RtspPanel
            onFrame={(d) => add(d.matches)}
            location="Entry"
            cameraId="entry-rtsp"
            eventType="entry"
          />
        </div>
      </section>

      <AccidentWorkerCard />

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 h-[520px]">
          <VehicleLog />
        </div>
        <div className="flex flex-col gap-6 lg:col-span-4 h-[520px]">
          <div className="flex-1 min-h-0">
            <MissingAlertsPanel />
          </div>
          <div className="flex-1 min-h-0">
            <InsideExitedPanel />
          </div>
        </div>
      </section>

      <Card>
        <CardHeader className="flex flex-col gap-3 space-y-0 border-b border-border/60 py-4 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <ScanSearch className="h-4 w-4 text-primary" />
            Live Recognition Stream
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2 text-[10px]">
            <Badge variant="muted" className="gap-1">
              <Activity className="h-3 w-3" />
              In window: {list.length}
            </Badge>
            <Badge variant="muted">
              Unique this session: {stats.total_unique}
            </Badge>
            <Badge variant={stats.last_face_ts ? "success" : "muted"}>
              Last face: {formatRelativeTime(
                stats.last_face_ts ? new Date(stats.last_face_ts).toISOString() : null
              )}
            </Badge>
            <Badge variant={stats.last_match_ts ? "success" : "muted"}>
              Last match: {formatRelativeTime(
                stats.last_match_ts ? new Date(stats.last_match_ts).toISOString() : null
              )}
            </Badge>
            {list.length ? (
              <Button variant="ghost" size="sm" onClick={clear}>
                <Trash2 className="h-3 w-3" />
                Clear
              </Button>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="p-5">
          <RecognitionFeed matches={list} expiryMs={RECOGNITION_EXPIRY_MS} />
        </CardContent>
      </Card>

      <AccidentFeed />
    </>
  );
}
