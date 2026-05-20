"use client";

import { useMemo, useRef, useState } from "react";
import { Camera, CheckCircle2, Loader2, Plus, Trash2, Upload, User, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePersons, useCreateProfile, useUpdatePersonTags } from "@/lib/hooks/usePersons";

const SUGGESTED_TAGS = ["suspect", "vip", "staff", "visitor", "banned"];

export default function ProfilesPage() {
  const { data: persons = [] } = usePersons();
  const createProfile = useCreateProfile();
  const updateTags = useUpdatePersonTags();

  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const tagPool = useMemo(() => {
    const set = new Set<string>();
    for (const p of persons) for (const t of p.tags || []) set.add(t);
    SUGGESTED_TAGS.forEach((t) => set.add(t));
    return Array.from(set).sort();
  }, [persons]);

  const onFileChange = (f: File | null) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  };

  const addTag = (t: string) => {
    const clean = t.trim();
    if (!clean) return;
    if (tags.some((x) => x.toLowerCase() === clean.toLowerCase())) return;
    setTags((prev) => [...prev, clean]);
    setNewTag("");
  };
  const removeTag = (t: string) => setTags((prev) => prev.filter((x) => x !== t));

  const reset = () => {
    setName("");
    setAge("");
    setPhone("");
    setAddress("");
    setNotes("");
    setTags([]);
    setNewTag("");
    onFileChange(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const canSubmit = !!name.trim() && !!file && !createProfile.isPending;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !file) return;
    try {
      const res = await createProfile.mutateAsync({
        name: name.trim(),
        file,
        age: age || undefined,
        address: address || undefined,
        phone: phone || undefined,
        notes: notes || undefined,
      });
      toast.success(`Profile created: ${res.name || name}`);

      if (tags.length && res.person_id) {
        try {
          await updateTags.mutateAsync({ personId: res.person_id, tags });
        } catch (err) {
          toast.warning(`Profile created, but failed to save tags: ${(err as Error).message}`);
        }
      }

      reset();
    } catch (err) {
      toast.error((err as Error).message || "Failed to create profile");
    }
  };

  return (
    <>
      <PageHeader
        title="Add Profile"
        description="Enroll a new identity. Upload a clear photo of the face — the backend will detect the face, compute an embedding, and store the profile."
      />

      <form onSubmit={submit} className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-2">
          <CardHeader className="border-b border-border/60 py-4">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Camera className="h-4 w-4 text-primary" />
              Face Photo
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-5">
            <div className="aspect-square w-full overflow-hidden rounded-md border border-dashed border-border/60 bg-background/40">
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewUrl}
                  alt="preview"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-muted-foreground">
                  <User className="h-10 w-10" />
                  <span className="text-xs">No photo selected</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <label className="flex h-9 cursor-pointer items-center gap-2 rounded-md border border-dashed border-input bg-background/50 px-3 text-sm text-muted-foreground hover:border-primary/50">
                <Upload className="h-4 w-4" />
                <span className="truncate">{file ? file.name : "Choose image"}</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
                />
              </label>
              {file ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    onFileChange(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              ) : null}
            </div>

            <div className="rounded-md border border-border/60 bg-background/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
              Tip: Use a clear, front-facing photo with good lighting. The API will reject images
              where no face is detected.
            </div>
          </CardContent>
        </Card>

        <Card className="xl:col-span-3">
          <CardHeader className="border-b border-border/60 py-4">
            <CardTitle className="text-sm">Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Full Name" required>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  required
                />
              </Field>
              <Field label="Age">
                <Input
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  placeholder="e.g. 34"
                  inputMode="numeric"
                />
              </Field>
              <Field label="Phone">
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+92 300 1234567"
                  inputMode="tel"
                />
              </Field>
              <Field label="Address">
                <Input
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Street, City"
                />
              </Field>
            </div>

            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional context — role, relationship, incident reference…"
                rows={3}
                className="flex w-full rounded-md border border-input bg-background/60 px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </Field>

            <div>
              <Label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Tags
              </Label>
              {tags.length ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {tags.map((t) => (
                    <Badge
                      key={t}
                      variant={t.toLowerCase() === "suspect" ? "destructive" : "muted"}
                      className="gap-1.5 pr-1.5"
                    >
                      {t}
                      <button
                        type="button"
                        onClick={() => removeTag(t)}
                        className="rounded-full p-0.5 hover:bg-black/20"
                        aria-label={`Remove ${t}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              ) : null}

              <div className="flex gap-2">
                <Input
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  placeholder="Add a tag and press Enter"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(newTag);
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => addTag(newTag)}
                  disabled={!newTag.trim()}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add
                </Button>
              </div>

              {tagPool.length ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {tagPool
                    .filter((t) => !tags.some((x) => x.toLowerCase() === t.toLowerCase()))
                    .slice(0, 16)
                    .map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => addTag(t)}
                        className="rounded-md border border-border/60 bg-background px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground transition hover:border-primary/60 hover:text-foreground"
                      >
                        + {t}
                      </button>
                    ))}
                </div>
              ) : null}
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-4">
              <div className="text-xs text-muted-foreground">
                {createProfile.isSuccess ? (
                  <span className="inline-flex items-center gap-1 text-[var(--color-success)]">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Last profile saved successfully.
                  </span>
                ) : (
                  <span>Required fields: name, photo.</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={reset}>
                  Reset
                </Button>
                <Button type="submit" size="sm" disabled={!canSubmit}>
                  {createProfile.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Upload className="h-3.5 w-3.5" />
                  )}
                  {createProfile.isPending ? "Enrolling…" : "Create profile"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </form>
    </>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
        {required ? <span className="ml-0.5 text-destructive">*</span> : null}
      </Label>
      {children}
    </div>
  );
}
