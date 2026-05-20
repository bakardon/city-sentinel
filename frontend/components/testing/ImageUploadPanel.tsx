"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileImage,
  Loader2,
  Trash2,
  Upload,
  UploadCloud,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiPostForm, artifactUrl } from "@/lib/api";
import { endpoints, type DetectionModule } from "@/lib/endpoints";
import { toast } from "sonner";
import { isPositiveLabel, useTestHistory } from "@/lib/stores/testHistory";
import type { ModuleTestImageResult } from "@/lib/types";

interface ImageUploadPanelProps {
  module: DetectionModule | "accident";
}

export function ImageUploadPanel({ module }: ImageUploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ModuleTestImageResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const addHistory = useTestHistory((s) => s.addItem);

  const endpoint =
    module === "accident"
      ? endpoints.accidentTest.image
      : endpoints.moduleTest(module).image;

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const assignFile = (f: File | null) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (!f) {
      setFile(null);
      setPreviewUrl(null);
      setResult(null);
      return;
    }
    if (!f.type.startsWith("image/")) {
      toast.error("Please drop an image file.");
      return;
    }
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    setResult(null);
  };

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    try {
      const form = new FormData();
      form.set("file", file);
      const res = await apiPostForm<ModuleTestImageResult>(endpoint, form);
      setResult(res);
      const pos = res.fire === true || isPositiveLabel(res.label) || isPositiveLabel(res.kind);
      addHistory({
        module: module as "fire" | "knife" | "weapon" | "violence" | "accident",
        kind: "image",
        filename: file.name,
        label: res.label ?? null,
        confidence: res.confidence ?? null,
        positive: pos,
        ok: res.ok,
        error: res.error ?? null,
        snapshot_url: res.artifact_url ?? null,
        clip_url: null,
      });
      if (res.ok) {
        toast.success(`Predicted: ${res.label ?? res.kind}`);
      } else {
        toast.error(res.error || "Prediction failed");
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const positive = useMemo(
    () =>
      result?.fire === true ||
      isPositiveLabel(result?.label) ||
      isPositiveLabel(result?.kind),
    [result]
  );
  const annotated = result?.artifact_url ? artifactUrl(result.artifact_url) : null;
  const conf = typeof result?.confidence === "number" ? result.confidence : null;

  const glow =
    result?.ok && positive ? "danger" : result?.ok && !positive ? "success" : "default";

  return (
    <Card glow={glow}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border/60 py-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          <FileImage className="h-4 w-4 text-primary" />
          Image Test
        </CardTitle>
        {file ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              assignFile(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4 p-5">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) assignFile(f);
          }}
          onClick={() => inputRef.current?.click()}
          className={`group relative flex min-h-[220px] cursor-pointer items-center justify-center overflow-hidden rounded-lg border-2 border-dashed transition ${
            dragOver
              ? "border-primary bg-primary/10"
              : "border-border/60 bg-background/40 hover:border-primary/60 hover:bg-primary/5"
          }`}
        >
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewUrl}
              alt="preview"
              className="max-h-[360px] w-full object-contain"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/30 transition group-hover:scale-110">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div className="text-sm font-medium text-foreground">
                Drop an image here
              </div>
              <div className="text-xs text-muted-foreground">
                or click to browse — JPG, PNG, WebP
              </div>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => assignFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
            {file ? file.name : "No file selected"}
          </div>
          <Button size="sm" onClick={submit} disabled={!file || loading}>
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            {loading ? "Analyzing…" : "Run detection"}
          </Button>
        </div>

        {result ? (
          <ResultPanel
            positive={positive}
            label={result.label ?? result.kind}
            confidence={conf}
            ok={result.ok}
            error={result.error}
            annotated={annotated}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}

function ResultPanel({
  positive,
  label,
  confidence,
  ok,
  error,
  annotated,
}: {
  positive: boolean;
  label?: string | null;
  confidence?: number | null;
  ok: boolean;
  error?: string | null;
  annotated?: string | null;
}) {
  const pct = confidence != null ? Math.max(0, Math.min(1, confidence)) * 100 : null;
  return (
    <div
      className={`space-y-3 rounded-lg border p-3 ${
        !ok
          ? "border-destructive/40 bg-destructive/5"
          : positive
          ? "border-destructive/40 bg-destructive/5"
          : "border-success/40 bg-success/5"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {ok ? (
          positive ? (
            <Badge variant="destructive" className="gap-1 uppercase">
              <AlertTriangle className="h-3 w-3" />
              Detected
            </Badge>
          ) : (
            <Badge variant="success" className="gap-1 uppercase">
              <CheckCircle2 className="h-3 w-3" />
              Clear
            </Badge>
          )
        ) : (
          <Badge variant="destructive" className="uppercase">
            Error
          </Badge>
        )}
        {label ? <Badge variant="muted">{label}</Badge> : null}
        {pct != null ? (
          <span className="font-mono text-xs text-muted-foreground">
            {pct.toFixed(1)}% confidence
          </span>
        ) : null}
      </div>

      {pct != null ? (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all ${
              positive ? "bg-destructive" : "bg-success"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : null}

      {annotated ? (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Annotated
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={annotated}
            alt="annotated"
            className="max-h-[360px] w-full rounded-md border border-border/60 bg-black object-contain"
          />
        </div>
      ) : null}

      {error ? (
        <div className="rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}
    </div>
  );
}
