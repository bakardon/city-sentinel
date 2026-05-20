import { DetectionModulePage } from "@/components/modules/DetectionModulePage";

export default function ViolenceDetectionPage() {
  return (
    <DetectionModulePage
      module="violence"
      title="Violence Detection"
      description="Live violence detection worker. Flags fights, assaults, and aggressive behavior in the camera stream."
      alertLabel="Violence"
    />
  );
}
