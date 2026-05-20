const NOISE_SVG = `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'>
    <filter id='n'>
      <feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>
      <feColorMatrix type='saturate' values='0'/>
      <feComponentTransfer><feFuncA type='linear' slope='0.55'/></feComponentTransfer>
    </filter>
    <rect width='100%' height='100%' filter='url(#n)' opacity='0.6'/>
  </svg>`
)}`;

export function SceneBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {/* Base wash — saturated night-ops gradient */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 120% 80% at 50% -10%, hsl(217 85% 22%) 0%, transparent 55%),
            radial-gradient(ellipse 100% 80% at 50% 120%, hsl(265 70% 20%) 0%, transparent 55%),
            linear-gradient(180deg, hsl(222 55% 7%) 0%, hsl(222 55% 4%) 100%)
          `,
        }}
      />

      {/* Fine tech grid — fully covers the viewport, bright blue lines */}
      <div
        className="absolute inset-0 animate-bg-grid-pan"
        style={{
          backgroundImage: `
            linear-gradient(to right, hsl(var(--primary) / 0.22) 1px, transparent 1px),
            linear-gradient(to bottom, hsl(var(--primary) / 0.22) 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px, 48px 48px",
        }}
      />

      {/* Coarse grid every 192px */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `
            linear-gradient(to right, hsl(var(--primary) / 0.38) 1px, transparent 1px),
            linear-gradient(to bottom, hsl(var(--primary) / 0.38) 1px, transparent 1px)
          `,
          backgroundSize: "192px 192px, 192px 192px",
        }}
      />

      {/* Aurora orb A — primary blue, top-left */}
      <div
        className="absolute left-[-15%] top-[-20%] h-[65vmax] w-[65vmax] animate-bg-drift-a rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, hsl(217 91% 60% / 0.55), hsl(217 91% 60% / 0) 60%)",
          filter: "blur(40px)",
        }}
      />

      {/* Aurora orb B — violet, bottom-right */}
      <div
        className="absolute bottom-[-25%] right-[-15%] h-[70vmax] w-[70vmax] animate-bg-drift-b rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, hsl(265 83% 62% / 0.5), hsl(265 83% 62% / 0) 60%)",
          filter: "blur(40px)",
        }}
      />

      {/* Aurora orb C — cyan, center */}
      <div
        className="absolute left-[25%] top-[15%] h-[50vmax] w-[50vmax] animate-bg-drift-c rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, hsl(190 85% 55% / 0.35), hsl(190 85% 55% / 0) 60%)",
          filter: "blur(40px)",
        }}
      />

      {/* Radar sweep — rotating conic wedge */}
      <div className="absolute left-1/2 top-1/2 -ml-[55vmax] -mt-[55vmax] h-[110vmax] w-[110vmax] animate-bg-radar opacity-70">
        <div
          className="h-full w-full"
          style={{
            background:
              "conic-gradient(from 0deg, transparent 0deg, hsl(var(--primary) / 0.65) 18deg, hsl(var(--primary) / 0.2) 38deg, transparent 60deg, transparent 360deg)",
            WebkitMaskImage:
              "radial-gradient(circle at 50% 50%, black 8%, black 48%, transparent 72%)",
            maskImage:
              "radial-gradient(circle at 50% 50%, black 8%, black 48%, transparent 72%)",
          }}
        />
      </div>

      {/* Radar rings — concentric circles */}
      <div
        className="absolute left-1/2 top-1/2 -ml-[40vmax] -mt-[40vmax] h-[80vmax] w-[80vmax] rounded-full opacity-30"
        style={{
          background:
            "repeating-radial-gradient(circle at 50% 50%, hsl(var(--primary) / 0.85) 0 1px, transparent 1px 100px)",
          WebkitMaskImage:
            "radial-gradient(circle at 50% 50%, black 20%, transparent 78%)",
          maskImage:
            "radial-gradient(circle at 50% 50%, black 20%, transparent 78%)",
        }}
      />

      {/* Crosshair at the radar center */}
      <div
        className="absolute left-1/2 top-1/2 -ml-[1px] h-[80vmax] w-[2px] -translate-y-1/2 opacity-20"
        style={{
          background:
            "linear-gradient(to bottom, transparent, hsl(var(--primary) / 0.6) 50%, transparent)",
        }}
      />
      <div
        className="absolute left-1/2 top-1/2 -mt-[1px] h-[2px] w-[80vmax] -translate-x-1/2 opacity-20"
        style={{
          background:
            "linear-gradient(to right, transparent, hsl(var(--primary) / 0.6) 50%, transparent)",
        }}
      />

      {/* Scanning line — horizontal sweep */}
      <div
        className="absolute inset-x-0 h-[3px] animate-bg-scan"
        style={{
          background:
            "linear-gradient(to right, transparent, hsl(var(--primary) / 0.9), transparent)",
          boxShadow: "0 0 20px 4px hsl(var(--primary) / 0.55)",
        }}
      />

      {/* CRT scanlines */}
      <div
        className="absolute inset-0 opacity-[0.06] mix-blend-overlay"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(255,255,255,0.7) 0 1px, transparent 1px 3px)",
        }}
      />

      {/* Grain/noise */}
      <div
        className="absolute inset-0 opacity-[0.08] mix-blend-overlay"
        style={{ backgroundImage: `url("${NOISE_SVG}")` }}
      />

      {/* Vignette — dark corners */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 45%, hsl(222 50% 3% / 0.75) 100%)",
        }}
      />
    </div>
  );
}
