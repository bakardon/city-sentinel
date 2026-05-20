import { TestModulePage } from "@/components/modules/TestModulePage";

export default function ViolenceTestPage() {
  return (
    <TestModulePage
      module="violence"
      title="Violence Test"
      description="Upload an image or video to run the violence detector offline and inspect annotated results."
    />
  );
}
