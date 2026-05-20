"use client";

import { useEffect, useState } from "react";
import { RotateCcw, Save } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { DEFAULT_SERVER_URL, useServerUrl } from "@/lib/stores/serverUrl";
import { toast } from "sonner";

export function ServerUrlInput() {
  const current = useServerUrl((s) => s.url);
  const setUrl = useServerUrl((s) => s.setUrl);
  const reset = useServerUrl((s) => s.reset);

  const [draft, setDraft] = useState(current);

  useEffect(() => {
    setDraft(current);
  }, [current]);

  const dirty = draft.trim() !== current;

  return (
    <div className="space-y-2">
      <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Backend URL
      </Label>
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        spellCheck={false}
        className="font-mono text-xs"
        placeholder={DEFAULT_SERVER_URL}
        onKeyDown={(e) => {
          if (e.key === "Enter" && dirty) {
            setUrl(draft.trim());
            toast.success("Backend URL updated");
          }
        }}
      />
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant={dirty ? "default" : "secondary"}
          disabled={!dirty}
          className="h-7 flex-1 text-xs"
          onClick={() => {
            setUrl(draft.trim());
            toast.success("Backend URL updated");
          }}
        >
          <Save className="h-3.5 w-3.5" />
          Save
        </Button>
        <Button
          size="icon"
          variant="ghost"
          title="Reset to default"
          className="h-7 w-7"
          onClick={() => {
            reset();
            toast.message(`Reset to ${DEFAULT_SERVER_URL}`);
          }}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
