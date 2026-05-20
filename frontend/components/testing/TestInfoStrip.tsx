"use client";

import { Brain, FileType2, Lightbulb, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

interface InfoItem {
  icon: LucideIcon;
  label: string;
  value: string;
}

interface TestInfoStripProps {
  detectedClasses: string;
  supportedFormats: string;
  tip: string;
}

export function TestInfoStrip({
  detectedClasses,
  supportedFormats,
  tip,
}: TestInfoStripProps) {
  const items: InfoItem[] = [
    { icon: Brain, label: "Model Detects", value: detectedClasses },
    { icon: FileType2, label: "Supported Formats", value: supportedFormats },
    { icon: Lightbulb, label: "Tip", value: tip },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {items.map((it) => {
        const Icon = it.icon;
        return (
          <Card key={it.label} className="p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/30">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {it.label}
                </div>
                <div className="mt-1 text-sm text-foreground">{it.value}</div>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
