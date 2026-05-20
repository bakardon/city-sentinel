"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Pencil, RotateCcw, Save, Video, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCameraPresets, type CameraPreset } from "@/lib/stores/cameraPresets";

const CUSTOM_VALUE = "__custom__";

export interface CameraPickerValue {
  rtsp_url: string;
  camera_id: string;
  camera_location: string;
}

interface CameraPresetPickerProps {
  value: CameraPickerValue;
  onChange: (next: CameraPickerValue) => void;
  disabled?: boolean;
  showLocation?: boolean;
}

export function CameraPresetPicker({
  value,
  onChange,
  disabled,
  showLocation,
}: CameraPresetPickerProps) {
  const presets = useCameraPresets((s) => s.presets);
  const updatePreset = useCameraPresets((s) => s.updatePreset);
  const resetPresets = useCameraPresets((s) => s.resetPresets);

  const [selectedId, setSelectedId] = useState<string>(CUSTOM_VALUE);
  const [editing, setEditing] = useState(false);
  const [draftPresets, setDraftPresets] = useState<CameraPreset[]>(presets);
  const editPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (editing) setDraftPresets(presets);
  }, [editing, presets]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!editing) return;
      if (editPanelRef.current && !editPanelRef.current.contains(e.target as Node)) {
        setEditing(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [editing]);

  const onSelect = (id: string) => {
    setSelectedId(id);
    if (id === CUSTOM_VALUE) return;
    const p = presets.find((x) => x.id === id);
    if (!p) return;
    onChange({
      rtsp_url: p.rtsp_url,
      camera_id: p.camera_id,
      camera_location: p.camera_location ?? "",
    });
  };

  const onCustomField = (patch: Partial<CameraPickerValue>) => {
    setSelectedId(CUSTOM_VALUE);
    onChange({ ...value, ...patch });
  };

  const saveDraft = () => {
    for (const p of draftPresets) {
      updatePreset(p.id, {
        label: p.label,
        rtsp_url: p.rtsp_url,
        camera_id: p.camera_id,
        camera_location: p.camera_location,
      });
    }
    setEditing(false);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Camera
        </Label>
        <button
          type="button"
          onClick={() => setEditing((v) => !v)}
          className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-background/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground transition hover:border-primary/60 hover:text-foreground"
        >
          <Pencil className="h-3 w-3" />
          Manage
        </button>
      </div>

      <div className="relative">
        <select
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled}
          className="h-8 w-full appearance-none rounded-md border border-input bg-background/60 pl-8 pr-8 text-xs font-medium text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} — {p.camera_id}
            </option>
          ))}
          <option value={CUSTOM_VALUE}>Custom URL…</option>
        </select>
        <Video className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      </div>

      <div className="grid gap-2">
        <Field label={`RTSP URL${selectedId !== CUSTOM_VALUE ? " (from preset)" : " (custom)"}`}>
          <Input
            value={value.rtsp_url}
            onChange={(e) => onCustomField({ rtsp_url: e.target.value })}
            placeholder="rtsp://user:pass@host:554/…"
            className="h-8 font-mono text-xs"
            disabled={disabled}
          />
        </Field>

        <div className={`grid gap-2 ${showLocation ? "md:grid-cols-2" : ""}`}>
          <Field label="Camera ID">
            <Input
              value={value.camera_id}
              onChange={(e) => onCustomField({ camera_id: e.target.value })}
              placeholder="e.g. cam_101"
              className="h-8 font-mono text-xs"
              disabled={disabled}
            />
          </Field>
          {showLocation ? (
            <Field label="Location">
              <Input
                value={value.camera_location}
                onChange={(e) => onCustomField({ camera_location: e.target.value })}
                placeholder="Main gate"
                className="h-8 font-mono text-xs"
                disabled={disabled}
              />
            </Field>
          ) : null}
        </div>
      </div>

      {editing ? (
        <div
          ref={editPanelRef}
          className="mt-2 space-y-3 rounded-md border border-primary/40 bg-card/95 p-3 shadow-[0_10px_30px_-10px_hsl(var(--primary)/0.5)] backdrop-blur"
        >
          <div className="flex items-center justify-between">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-primary">
              Manage Camera Presets
            </div>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="space-y-3">
            {draftPresets.map((p, idx) => (
              <div key={p.id} className="rounded-md border border-border/60 bg-background/40 p-3">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {p.id}
                </div>
                <div className="grid gap-2">
                  <Field label="Label">
                    <Input
                      value={p.label}
                      onChange={(e) => {
                        const next = [...draftPresets];
                        next[idx] = { ...p, label: e.target.value };
                        setDraftPresets(next);
                      }}
                      className="h-8 text-xs"
                    />
                  </Field>
                  <Field label="RTSP URL">
                    <Input
                      value={p.rtsp_url}
                      onChange={(e) => {
                        const next = [...draftPresets];
                        next[idx] = { ...p, rtsp_url: e.target.value };
                        setDraftPresets(next);
                      }}
                      className="h-8 font-mono text-xs"
                    />
                  </Field>
                  <div className="grid gap-2 md:grid-cols-2">
                    <Field label="Camera ID">
                      <Input
                        value={p.camera_id}
                        onChange={(e) => {
                          const next = [...draftPresets];
                          next[idx] = { ...p, camera_id: e.target.value };
                          setDraftPresets(next);
                        }}
                        className="h-8 font-mono text-xs"
                      />
                    </Field>
                    <Field label="Location">
                      <Input
                        value={p.camera_location ?? ""}
                        onChange={(e) => {
                          const next = [...draftPresets];
                          next[idx] = { ...p, camera_location: e.target.value };
                          setDraftPresets(next);
                        }}
                        className="h-8 font-mono text-xs"
                      />
                    </Field>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-border/60 pt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                resetPresets();
                setDraftPresets(presets);
              }}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset defaults
            </Button>
            <Button type="button" size="sm" onClick={saveDraft}>
              <Save className="h-3.5 w-3.5" />
              Save
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}
