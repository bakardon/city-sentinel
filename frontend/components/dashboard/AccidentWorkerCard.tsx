"use client";

import { AlertCircle } from "lucide-react";
import { WorkerControls } from "@/components/workers/WorkerControls";
import { useAccidentWorkerStatus } from "@/lib/hooks/useWorkerStatus";
import { useAccidentWorkerMutations } from "@/lib/hooks/useWorkerMutations";

export function AccidentWorkerCard() {
  const { data: status } = useAccidentWorkerStatus();
  const { start, stop } = useAccidentWorkerMutations();

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 text-destructive" />
        <h2 className="text-sm font-semibold">Accident Detection Worker</h2>
      </div>
      <WorkerControls
        title="Accident Worker"
        status={status}
        onStart={(p) => start.mutate(p)}
        onStop={() => stop.mutate()}
        isStarting={start.isPending}
        isStopping={stop.isPending}
      />
    </div>
  );
}
