export type DetectionModule = "fire" | "knife" | "weapon" | "violence";

export const endpoints = {
  health: "/health",

  persons: "/persons",
  person: (id: string) => `/persons/${encodeURIComponent(id)}`,
  personTags: (id: string) => `/persons/${encodeURIComponent(id)}/tags`,
  profiles: "/profiles",

  vehiclesEvents: "/vehicles/events",
  missingAlerts: "/alerts/missing",

  accidents: "/accidents",
  accidentWorker: {
    status: "/accident-worker/status",
    start: "/accident-worker/start",
    stop: "/accident-worker/stop",
  },
  accidentTest: {
    image: "/accident-test/image",
    video: "/accident-test/video",
    artifact: (rel: string) => `/accident-test/artifacts/${rel.replace(/^\/+/, "")}`,
  },

  fireEvents: "/fire-events",
  knifeEvents: "/knife-events",
  weaponEvents: "/weapon-events",
  violenceEvents: "/violence-events",

  worker: (m: DetectionModule) => ({
    status: `/${m}-worker/status`,
    start: `/${m}-worker/start`,
    stop: `/${m}-worker/stop`,
    frame: `/${m}-worker/frame`,
  }),

  moduleTest: (m: DetectionModule) => ({
    image: `/${m}-test/image`,
    video: `/${m}-test/video`,
    artifact: (rel: string) => `/${m}-test/artifacts/${rel.replace(/^\/+/, "")}`,
  }),

  recognizePerson: "/recognize/person",
  recognizeRtsp: "/recognize/rtsp",
} as const;

export function eventsEndpointFor(m: DetectionModule): string {
  switch (m) {
    case "fire":
      return endpoints.fireEvents;
    case "knife":
      return endpoints.knifeEvents;
    case "weapon":
      return endpoints.weaponEvents;
    case "violence":
      return endpoints.violenceEvents;
  }
}
