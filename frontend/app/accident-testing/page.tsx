import { TestModulePage } from "@/components/modules/TestModulePage";

export default function AccidentTestingPage() {
  return (
    <TestModulePage
      module="accident"
      title="Accident Testing"
      description="Upload an image or video to run the accident classifier and review the generated snapshot and clip artifacts."
    />
  );
}
