import { DetectionModulePage } from "@/components/modules/DetectionModulePage";

export default function FireDetectionPage() {
  return (
    <DetectionModulePage
      module="fire"
      title="Fire Detection"
      description="Live fire and smoke detection worker. Monitors an RTSP stream and raises alerts when fire or smoke is detected with high confidence."
      alertLabel="Fire"
    />
  );
}
