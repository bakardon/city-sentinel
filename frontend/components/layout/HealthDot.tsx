"use client";

import { useHealth } from "@/lib/hooks/useHealth";
import { cn } from "@/lib/utils";

export function HealthDot() {
  const { data, isLoading, isError } = useHealth();
  const online = !isError && !!data;

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "relative flex h-2 w-2",
          online ? "text-success" : isLoading ? "text-warning" : "text-destructive"
        )}
      >
        <span
          className={cn(
            "absolute inline-flex h-full w-full rounded-full opacity-75",
            online && "animate-ping bg-success",
            !online && !isLoading && "bg-destructive",
            isLoading && "bg-warning"
          )}
        />
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            online && "bg-success",
            !online && !isLoading && "bg-destructive",
            isLoading && "bg-warning"
          )}
        />
      </span>
      <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {online ? "System Online" : isLoading ? "Checking…" : "Backend Unreachable"}
      </span>
    </div>
  );
}
