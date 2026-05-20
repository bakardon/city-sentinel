import { Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ComingSoon({ title, description }: { title: string; description?: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center gap-3 p-16 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-warning/15 text-warning">
          <Construction className="h-7 w-7" />
        </div>
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            {description ||
              "This section will ship in phase 2 of the Next.js rebuild. All features from the original dashboard will be restored — they just haven't been migrated yet."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
