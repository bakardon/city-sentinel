import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { SceneBackground } from "@/components/layout/SceneBackground";
import { Providers } from "@/lib/providers";

export const metadata: Metadata = {
  title: "City Sentinel",
  description: "AI surveillance dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="relative min-h-screen bg-background font-sans text-foreground antialiased">
        <SceneBackground />
        <Providers>
          <div className="relative flex min-h-screen">
            <Sidebar />
            <main className="min-w-0 flex-1 overflow-x-hidden">
              <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-6 px-6 py-6">
                {children}
              </div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
