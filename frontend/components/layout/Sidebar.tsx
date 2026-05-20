"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  AlertOctagon,
  Flame,
  TestTubeDiagonal,
  Crosshair,
  ShieldAlert,
  Users,
  Tag,
  UserPlus,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ServerUrlInput } from "@/components/layout/ServerUrlInput";
import { HealthDot } from "@/components/layout/HealthDot";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  group: "main" | "detection" | "testing" | "people";
}

const NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, group: "main" },
  { label: "Accident Testing", href: "/accident-testing", icon: AlertOctagon, group: "testing" },
  { label: "Fire Detection", href: "/fire-detection", icon: Flame, group: "detection" },
  { label: "Fire Test", href: "/fire-test", icon: TestTubeDiagonal, group: "testing" },
  { label: "Armed Detection", href: "/armed-detection", icon: Crosshair, group: "detection" },
  { label: "Knife Test", href: "/knife-test", icon: TestTubeDiagonal, group: "testing" },
  { label: "Weapon Test", href: "/weapon-test", icon: TestTubeDiagonal, group: "testing" },
  { label: "Violence Detection", href: "/violence-detection", icon: ShieldAlert, group: "detection" },
  { label: "Violence Test", href: "/violence-test", icon: TestTubeDiagonal, group: "testing" },
  { label: "Database", href: "/persons", icon: Users, group: "people" },
  { label: "Tagging", href: "/tags", icon: Tag, group: "people" },
  { label: "Add Profile", href: "/profiles", icon: UserPlus, group: "people" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col border-r border-border/60 bg-card/40 backdrop-blur">
      <div className="flex h-16 items-center gap-3 border-b border-border/60 px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight">City Sentinel</span>
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Surveillance Console
          </span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-1">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-border/60 bg-background/60 p-4">
        <div className="mb-3 flex items-center gap-2">
          <HealthDot />
        </div>
        <ServerUrlInput />
      </div>
    </aside>
  );
}
