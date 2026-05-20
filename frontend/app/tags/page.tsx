"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Save, Search, Tag, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { PersonCard } from "@/components/persons/PersonCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePersons, useUpdatePersonTags } from "@/lib/hooks/usePersons";
import type { PersonRecord } from "@/lib/types";

const SUGGESTED_TAGS = ["suspect", "vip", "staff", "visitor", "banned", "alert"];

export default function TagsPage() {
  const { data: persons = [], isLoading } = usePersons();
  const update = useUpdatePersonTags();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<PersonRecord | null>(null);
  const [draft, setDraft] = useState<string[]>([]);
  const [newTag, setNewTag] = useState("");

  useEffect(() => {
    setDraft(selected?.tags || []);
  }, [selected]);

  const existingTagPool = useMemo(() => {
    const set = new Set<string>();
    for (const p of persons) for (const t of p.tags || []) set.add(t);
    SUGGESTED_TAGS.forEach((t) => set.add(t));
    return Array.from(set).sort();
  }, [persons]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return persons;
    return persons.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(q) ||
        (p.phone || "").toLowerCase().includes(q) ||
        (p.tags || []).some((t) => t.toLowerCase().includes(q))
    );
  }, [persons, query]);

  const addTag = (t: string) => {
    const clean = t.trim();
    if (!clean) return;
    if (draft.some((x) => x.toLowerCase() === clean.toLowerCase())) return;
    setDraft((d) => [...d, clean]);
    setNewTag("");
  };
  const removeTag = (t: string) => setDraft((d) => d.filter((x) => x !== t));

  const dirty =
    !!selected &&
    (draft.length !== (selected.tags || []).length ||
      draft.some((t, i) => t !== (selected.tags || [])[i]));

  const save = async () => {
    if (!selected) return;
    try {
      await update.mutateAsync({ personId: selected.id, tags: draft });
      toast.success(`Tags updated for ${selected.name || selected.id}`);
      setSelected({ ...selected, tags: [...draft] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Tag Management"
        description="Assign tags like suspect, VIP, or staff to enrolled persons. Changes persist to the backend."
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-col gap-3 space-y-0 border-b border-border/60 py-4 md:flex-row md:items-center md:justify-between">
            <CardTitle className="text-sm">Select Person</CardTitle>
            <div className="relative w-full md:w-56">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search"
                className="h-9 pl-8"
              />
            </div>
          </CardHeader>
          <CardContent className="max-h-[70vh] space-y-2 overflow-y-auto p-4">
            {isLoading ? (
              <div className="flex h-40 items-center justify-center text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border/60 text-xs text-muted-foreground">
                No persons found.
              </div>
            ) : (
              filtered.map((p) => (
                <PersonCard
                  key={p.id}
                  person={p}
                  compact
                  selected={selected?.id === p.id}
                  onClick={() => setSelected(p)}
                />
              ))
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader className="border-b border-border/60 py-4">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Tag className="h-4 w-4 text-primary" />
              Edit Tags
              {selected ? (
                <span className="text-muted-foreground">· {selected.name || selected.id}</span>
              ) : null}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-5">
            {!selected ? (
              <div className="flex h-56 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 text-sm text-muted-foreground">
                <Tag className="h-6 w-6" />
                <span>Pick a person on the left to edit their tags.</span>
              </div>
            ) : (
              <>
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Current Tags
                  </div>
                  {draft.length === 0 ? (
                    <div className="rounded-md border border-dashed border-border/60 px-3 py-4 text-xs text-muted-foreground">
                      No tags assigned.
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {draft.map((t) => (
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
                  )}
                </div>

                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Add Tag
                  </div>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      addTag(newTag);
                    }}
                    className="flex gap-2"
                  >
                    <Input
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      placeholder="e.g. suspect, vip, staff"
                      className="h-9"
                    />
                    <Button type="submit" size="sm" variant="secondary" disabled={!newTag.trim()}>
                      <Plus className="h-3.5 w-3.5" />
                      Add
                    </Button>
                  </form>
                </div>

                {existingTagPool.length ? (
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Quick Pick
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {existingTagPool
                        .filter((t) => !draft.some((x) => x.toLowerCase() === t.toLowerCase()))
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
                  </div>
                ) : null}

                <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDraft(selected.tags || [])}
                    disabled={!dirty}
                  >
                    Reset
                  </Button>
                  <Button size="sm" onClick={save} disabled={!dirty || update.isPending}>
                    {update.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    Save changes
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
