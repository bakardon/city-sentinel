"use client";

import type { RecognitionMatch, RecognitionPlate } from "@/lib/types";

export function FaceBoxOverlay({
  match,
  canvasW,
  canvasH,
}: {
  match: RecognitionMatch;
  canvasW: number;
  canvasH: number;
}) {
  const box = match.box;
  if (!box) return null;
  const { x1, y1, x2, y2 } = box;
  const w = Math.max(1, x2 - x1);
  const h = Math.max(1, y2 - y1);

  const isKnown = !!match.person_id;
  const tagSuspect = (match.tags || []).some((t) => t.toLowerCase() === "suspect");
  const color = tagSuspect ? "#ef4444" : isKnown ? "#22c55e" : "#eab308";

  const scorePct =
    typeof match.similarity === "number"
      ? ` ${(match.similarity * 100).toFixed(0)}%`
      : "";
  const label = (match.name || (isKnown ? "Unnamed" : "Unknown")) + scorePct;
  const primaryTag = (match.tags || [])[0];

  const scale = Math.max(canvasW, canvasH) / 640;
  const strokeW = 3 * scale;
  const cornerLen = Math.min(w, h) * 0.22;
  const labelFontSize = Math.max(14, 18 * scale);
  const tagFontSize = Math.max(11, 14 * scale);
  const labelPadX = 8 * scale;
  const labelPadY = 6 * scale;
  const charW = labelFontSize * 0.58;
  const labelW = labelPadX * 2 + Math.max(label.length, 6) * charW;
  const labelH = labelFontSize + labelPadY * 2;
  const labelY = Math.max(0, y1 - labelH - 4);

  return (
    <g>
      <rect
        x={x1}
        y={y1}
        width={w}
        height={h}
        fill="none"
        stroke={color}
        strokeWidth={strokeW}
        rx={6}
        opacity={0.35}
      />
      <Corner x={x1} y={y1} len={cornerLen} dx={1} dy={1} color={color} w={strokeW} />
      <Corner x={x2} y={y1} len={cornerLen} dx={-1} dy={1} color={color} w={strokeW} />
      <Corner x={x1} y={y2} len={cornerLen} dx={1} dy={-1} color={color} w={strokeW} />
      <Corner x={x2} y={y2} len={cornerLen} dx={-1} dy={-1} color={color} w={strokeW} />

      <rect
        x={x1}
        y={labelY}
        width={labelW}
        height={labelH}
        fill="rgba(0,0,0,0.78)"
        stroke={color}
        strokeWidth={Math.max(1, strokeW * 0.5)}
        rx={4}
      />
      <text
        x={x1 + labelPadX}
        y={labelY + labelPadY + labelFontSize * 0.8}
        fill="#fff"
        fontSize={labelFontSize}
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fontWeight={600}
      >
        {label}
      </text>

      {primaryTag ? (
        <g>
          <rect
            x={x1}
            y={labelY + labelH + 2}
            width={Math.max(30 * scale, (primaryTag.length + 2) * tagFontSize * 0.6)}
            height={tagFontSize + labelPadY}
            fill={tagSuspect ? "#dc2626" : "#1e3a8a"}
            rx={3}
          />
          <text
            x={x1 + 6 * scale}
            y={labelY + labelH + 2 + (tagFontSize + labelPadY) * 0.75}
            fill="#fff"
            fontSize={tagFontSize}
            fontFamily="ui-sans-serif, system-ui, sans-serif"
            fontWeight={700}
            letterSpacing="0.5"
          >
            {primaryTag.toUpperCase()}
          </text>
        </g>
      ) : null}
    </g>
  );
}

function Corner({
  x,
  y,
  len,
  dx,
  dy,
  color,
  w,
}: {
  x: number;
  y: number;
  len: number;
  dx: 1 | -1;
  dy: 1 | -1;
  color: string;
  w: number;
}) {
  return (
    <g>
      <line
        x1={x}
        y1={y}
        x2={x + len * dx}
        y2={y}
        stroke={color}
        strokeWidth={w}
        strokeLinecap="round"
      />
      <line
        x1={x}
        y1={y}
        x2={x}
        y2={y + len * dy}
        stroke={color}
        strokeWidth={w}
        strokeLinecap="round"
      />
    </g>
  );
}

export function PlateBoxOverlay({
  plate,
  canvasW,
  canvasH,
}: {
  plate: RecognitionPlate;
  canvasW: number;
  canvasH: number;
}) {
  const b = plate.box;
  if (!b) return null;
  const w = Math.max(1, b.x2 - b.x1);
  const h = Math.max(1, b.y2 - b.y1);
  const scale = Math.max(canvasW, canvasH) / 640;
  const strokeW = 3 * scale;
  const fontSize = Math.max(14, 16 * scale);
  const labelPadX = 8 * scale;
  const labelPadY = 5 * scale;
  const text = plate.text || "PLATE";
  const labelW = labelPadX * 2 + text.length * fontSize * 0.6;
  const labelH = fontSize + labelPadY * 2;
  const labelY = b.y2 + 4;
  return (
    <g>
      <rect
        x={b.x1}
        y={b.y1}
        width={w}
        height={h}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={strokeW}
        rx={4}
      />
      <rect
        x={b.x1}
        y={labelY}
        width={labelW}
        height={labelH}
        fill="rgba(0,0,0,0.8)"
        stroke="#3b82f6"
        strokeWidth={Math.max(1, strokeW * 0.5)}
        rx={3}
      />
      <text
        x={b.x1 + labelPadX}
        y={labelY + labelPadY + fontSize * 0.8}
        fill="#93c5fd"
        fontSize={fontSize}
        fontFamily="ui-monospace, monospace"
        fontWeight={700}
        letterSpacing="1"
      >
        {text}
      </text>
    </g>
  );
}
