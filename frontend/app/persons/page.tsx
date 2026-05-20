"use client";

import { useMemo, useState } from "react";
import {
  Loader2,
  RefreshCw,
  Search,
  Users,
  AlertTriangle,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { PersonCard } from "@/components/persons/PersonCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useDeletePerson, usePersons } from "@/lib/hooks/usePersons";
import type { PersonRecord } from "@/lib/types";

export default function PersonsPage() {
  const { data: persons = [], isLoading, isFetching, refetch } = usePersons();
  const deleteMutation = useDeletePerson();
  const [query, setQuery] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [selected, setSelected] = useState<PersonRecord | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const handleDelete = async (person: PersonRecord) => {
    try {
      await deleteMutation.mutateAsync(person.id);
      toast.success(`Removed ${person.name || "person"} from database`);
      setSelected((cur) => (cur?.id === person.id ? null : cur));
      setConfirmId(null);
    } catch (err) {
      toast.error((err as Error).message || "Failed to delete person");
    }
  };

  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const p of persons) for (const t of p.tags || []) set.add(t);
    return Array.from(set).sort();
  }, [persons]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return persons.filter((p) => {
      if (activeTag && !(p.tags || []).some((t) => t.toLowerCase() === activeTag.toLowerCase())) return false;
      if (!q) return true;
      return (
        (p.name || "").toLowerCase().includes(q) ||
        (p.phone || "").toLowerCase().includes(q) ||
        (p.address || "").toLowerCase().includes(q) ||
        (p.notes || "").toLowerCase().includes(q) ||
        (p.tags || []).some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [persons, query, activeTag]);

  return (
    <>
      <PageHeader
        title="Persons Database"
        description="Browse enrolled identities, search by name or metadata, and filter by tag."
        actions={
          <Button
            size="sm"
            variant="secondary"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-col gap-3 space-y-0 border-b border-border/60 py-4 md:flex-row md:items-center md:justify-between">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Users className="h-4 w-4 text-primary" />
              {filtered.length} {filtered.length === 1 ? "Person" : "People"}
              {activeTag ? (
                <Badge variant="muted" className="ml-2">
                  tag: {activeTag}
                </Badge>
              ) : null}
            </CardTitle>
            <div className="relative w-full md:w-72">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name, phone, tag…"
                className="h-9 pl-8"
              />
            </div>
          </CardHeader>

          {allTags.length ? (
            <div className="flex flex-wrap gap-1.5 border-b border-border/60 bg-background/40 px-5 py-3">
              <button
                onClick={() => setActiveTag(null)}
                className={`rounded-md border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition ${
                  !activeTag
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border/60 bg-background text-muted-foreground hover:border-primary/50"
                }`}
              >
                All
              </button>
              {allTags.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTag(t === activeTag ? null : t)}
                  className={`rounded-md border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition ${
                    t === activeTag
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border/60 bg-background text-muted-foreground hover:border-primary/50"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          ) : null}

          <CardContent className="p-5">
            {isLoading ? (
              <div className="flex h-40 items-center justify-center text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading persons…
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 text-sm text-muted-foreground">
                <Users className="h-6 w-6" />
                <span>No people match the current filter.</span>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {filtered.map((p) => (
                  <PersonCard
                    key={p.id}
                    person={p}
                    selected={selected?.id === p.id}
                    onClick={() => setSelected(p)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:sticky lg:top-6 lg:h-fit">
          <CardHeader className="border-b border-border/60 py-4">
            <CardTitle className="text-sm">Details</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            {!selected ? (
              <div className="flex h-40 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
                <AlertTriangle className="h-5 w-5" />
                <span>Select a person to view full details.</span>
              </div>
            ) : (
              <div className="space-y-4">
                {selected.image_b64 ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`data:image/jpeg;base64,${selected.image_b64}`}
                    alt={selected.name ?? "person"}
                    className="aspect-square w-full rounded-md border border-border/60 bg-black object-cover"
                  />
                ) : null}
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Name
                  </div>
                  <div className="text-sm font-medium">{selected.name || "—"}</div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <DetailItem label="Age" value={selected.age} />
                  <DetailItem label="Phone" value={selected.phone} />
                </div>
                <DetailItem label="Address" value={selected.address} />
                <DetailItem label="Notes" value={selected.notes} />
                <div>
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Tags
                  </div>
                  {(selected.tags || []).length ? (
                    <div className="flex flex-wrap gap-1">
                      {(selected.tags || []).map((t) => (
                        <Badge
                          key={t}
                          variant={t.toLowerCase() === "suspect" ? "destructive" : "muted"}
                        >
                          {t}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </div>
                <div className="rounded-md border border-dashed border-border/60 bg-background/40 p-2 text-[10px] font-mono text-muted-foreground">
                  id: {selected.id}
                </div>

                <div className="pt-2">
                  {confirmId !== selected.id ? (
                    <Button
                      variant="destructive"
                      size="sm"
                      className="w-full"
                      onClick={() => setConfirmId(selected.id)}
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Remove person
                    </Button>
                  ) : (
                    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 space-y-2">
                      <div className="flex items-start gap-2 text-xs text-destructive">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>
                          Permanently remove{" "}
                          <span className="font-semibold">{selected.name || "this person"}</span>{" "}
                          and their face embedding? This cannot be undone.
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="destructive"
                          size="sm"
                          className="flex-1"
                          onClick={() => handleDelete(selected)}
                          disabled={deleteMutation.isPending}
                        >
                          {deleteMutation.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                          Confirm delete
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="flex-1"
                          onClick={() => setConfirmId(null)}
                          disabled={deleteMutation.isPending}
                        >
                          <X className="h-3.5 w-3.5" />
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function DetailItem({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-sm">{value || <span className="text-muted-foreground">—</span>}</div>
    </div>
  );
}
