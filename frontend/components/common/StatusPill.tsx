import { cn } from "@/lib/utils";

type StatusKind = "running" | "stopped" | "error" | "idle";

export function StatusPill({
  state,
  label,
  className,
}: {
  state: StatusKind;
  label?: string;
  className?: string;
}) {
  const palette: Record<StatusKind, string> = {
    running: "bg-success/15 text-success border-success/30",
    stopped: "bg-muted text-muted-foreground border-border",
    error: "bg-destructive/15 text-destructive border-destructive/30",
    idle: "bg-warning/15 text-warning border-warning/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold",
        palette[state],
        className
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          state === "running" && "bg-success animate-pulse",
          state === "stopped" && "bg-muted-foreground",
          state === "error" && "bg-destructive",
          state === "idle" && "bg-warning"
        )}
      />
      {label ?? state.toUpperCase()}
    </span>
  );
}
