"use client";

import { History, Trash2, FileImage, FileVideo, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { artifactUrl } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import { useTestHistory, type TestModuleKey } from "@/lib/stores/testHistory";

interface TestHistoryPanelProps {
  module: TestModuleKey;
}

export function TestHistoryPanel({ module }: TestHistoryPanelProps) {
  const allItems = useTestHistory((s) => s.items);
  const clear = useTestHistory((s) => s.clear);
  const items = allItems.filter((i) => i.module === module);

  const positives = items.filter((i) => i.positive && i.ok).length;
  const negatives = items.filter((i) => !i.positive && i.ok).length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border/60 py-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          <History className="h-4 w-4 text-primary" />
          Session History
          <span className="text-muted-foreground">· {items.length}</span>
          {items.length ? (
            <>
              <Badge variant="destructive" className="ml-2 text-[9px]">
                {positives} detected
              </Badge>
              <Badge variant="success" className="text-[9px]">
                {negatives} clear
              </Badge>
            </>
          ) : null}
        </CardTitle>
        {items.length ? (
          <Button variant="ghost" size="sm" onClick={() => clear(module)}>
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="p-5">
        {items.length === 0 ? (
          <div className="flex h-28 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
            <History className="h-5 w-5" />
            <span>No tests run yet in this session.</span>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
            {items.map((item) => {
              const thumb = item.snapshot_url ? artifactUrl(item.snapshot_url) : null;
              const pct =
                item.confidence != null
                  ? Math.max(0, Math.min(1, item.confidence)) * 100
                  : null;
              return (
                <div
                  key={item.id}
                  className={`overflow-hidden rounded-lg border text-left transition ${
                    item.positive
                      ? "border-destructive/40"
                      : item.ok
                      ? "border-success/40"
                      : "border-border/60"
                  }`}
                >
                  <div className="relative aspect-video bg-black">
                    {thumb ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={thumb}
                        alt={item.filename}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-muted-foreground">
                        {item.kind === "video" ? (
                          <FileVideo className="h-6 w-6" />
                        ) : (
                          <FileImage className="h-6 w-6" />
                        )}
                      </div>
                    )}
                    <div className="absolute left-1.5 top-1.5">
                      {item.ok ? (
                        item.positive ? (
                          <Badge variant="destructive" className="gap-1 text-[9px]">
                            <AlertTriangle className="h-2.5 w-2.5" />
                            Detected
                          </Badge>
                        ) : (
                          <Badge variant="success" className="gap-1 text-[9px]">
                            <CheckCircle2 className="h-2.5 w-2.5" />
                            Clear
                          </Badge>
                        )
                      ) : (
                        <Badge variant="destructive" className="text-[9px]">
                          Error
                        </Badge>
                      )}
                    </div>
                    <div className="absolute right-1.5 top-1.5">
                      <Badge variant="muted" className="gap-1 text-[9px] uppercase">
                        {item.kind === "video" ? (
                          <FileVideo className="h-2.5 w-2.5" />
                        ) : (
                          <FileImage className="h-2.5 w-2.5" />
                        )}
                        {item.kind}
                      </Badge>
                    </div>
                  </div>
                  <div className="space-y-1.5 p-2.5">
                    <div className="truncate font-mono text-[10px] text-muted-foreground">
                      {item.filename}
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium">
                        {item.label ?? (item.ok ? "clear" : "error")}
                      </span>
                      {pct != null ? (
                        <span
                          className={`font-mono text-[10px] ${
                            item.positive
                              ? "text-destructive"
                              : item.ok
                              ? "text-success"
                              : "text-muted-foreground"
                          }`}
                        >
                          {pct.toFixed(0)}%
                        </span>
                      ) : null}
                    </div>
                    {pct != null ? (
                      <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full ${
                            item.positive ? "bg-destructive" : "bg-success"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    ) : null}
                    <div className="text-[10px] text-muted-foreground">
                      {formatRelativeTime(new Date(item.created_at).toISOString())}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
