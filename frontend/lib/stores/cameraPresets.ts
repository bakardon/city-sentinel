"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface CameraPreset {
  id: string;
  label: string;
  rtsp_url: string;
  camera_id: string;
  camera_location?: string;
}

const DEFAULT_PRESETS: CameraPreset[] = [
  {
    id: "cam_1",
    label: "Camera 1",
    rtsp_url: "rtsp://admin:fcse1234@10.1.139.235:554/Streaming/Channels/101",
    camera_id: "cam_1",
    camera_location: "Main Gate",
  },
  {
    id: "cam_2",
    label: "Camera 2",
    rtsp_url: "rtsp://admin:fcse1234@10.1.139.235:554/Streaming/Channels/201",
    camera_id: "cam_2",
    camera_location: "Parking Lot",
  },
];

interface CameraPresetState {
  presets: CameraPreset[];
  updatePreset: (id: string, patch: Partial<Omit<CameraPreset, "id">>) => void;
  resetPresets: () => void;
}

export const useCameraPresets = create<CameraPresetState>()(
  persist(
    (set) => ({
      presets: DEFAULT_PRESETS,
      updatePreset: (id, patch) =>
        set((s) => ({
          presets: s.presets.map((p) => (p.id === id ? { ...p, ...patch } : p)),
        })),
      resetPresets: () => set({ presets: DEFAULT_PRESETS }),
    }),
    {
      name: "city-sentinel.cameraPresets",
      version: 1,
    }
  )
);
