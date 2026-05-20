"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPostForm } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";
import { useServerUrl } from "@/lib/stores/serverUrl";
import type { PersonRecord } from "@/lib/types";

export function usePersons() {
  const serverUrl = useServerUrl((s) => s.url);
  return useQuery({
    queryKey: ["persons", serverUrl],
    queryFn: async ({ signal }) => {
      const res = await apiGet<{ persons: PersonRecord[] }>(endpoints.persons, undefined, signal);
      return res.persons || [];
    },
    refetchInterval: 30000,
    staleTime: 15000,
  });
}

export function useUpdatePersonTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ personId, tags }: { personId: string; tags: string[] }) => {
      const form = new FormData();
      form.set("tags", tags.join(","));
      return apiPostForm<{ person_id: string; tags: string[] }>(endpoints.personTags(personId), form);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}

export interface CreateProfileInput {
  name: string;
  file: File;
  age?: string;
  address?: string;
  phone?: string;
  notes?: string;
}

export function useDeletePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (personId: string) => {
      return apiDelete<{ person_id: string; deleted: boolean }>(endpoints.person(personId));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateProfileInput) => {
      const form = new FormData();
      form.set("name", input.name);
      form.set("file", input.file);
      if (input.age) form.set("age", input.age);
      if (input.address) form.set("address", input.address);
      if (input.phone) form.set("phone", input.phone);
      if (input.notes) form.set("notes", input.notes);
      return apiPostForm<PersonRecord & { person_id: string }>(endpoints.profiles, form);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["persons"] });
    },
  });
}
