"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { ImageUploadPanel } from "@/components/testing/ImageUploadPanel";
import { VideoUploadPanel } from "@/components/testing/VideoUploadPanel";
import { TestInfoStrip } from "@/components/testing/TestInfoStrip";
import { TestHistoryPanel } from "@/components/testing/TestHistoryPanel";
import type { DetectionModule } from "@/lib/endpoints";
import type { TestModuleKey } from "@/lib/stores/testHistory";

type AnyTestModule = DetectionModule | "accident";

interface TestModulePageProps {
  module: AnyTestModule;
  title: string;
  description: string;
}

interface ModuleContent {
  detectedClasses: string;
  supportedFormats: string;
  tip: string;
}

const MODULE_CONTENT: Record<AnyTestModule, ModuleContent> = {
  fire: {
    detectedClasses: "Open flames, smoke plumes, and active fire events.",
    supportedFormats: "Images: JPG, PNG, WebP · Video: MP4, WebM, MOV",
    tip: "Bright daylight scenes with no flame should classify as clear; low-light or backlit imagery can raise false positives.",
  },
  knife: {
    detectedClasses: "Kitchen knives, combat knives, and other bladed weapons.",
    supportedFormats: "Images: JPG, PNG, WebP · Video: MP4, WebM, MOV",
    tip: "Use well-lit, unobstructed shots — partial or heavily occluded blades may not be detected reliably.",
  },
  weapon: {
    detectedClasses: "Handguns, rifles, shotguns, and other firearms.",
    supportedFormats: "Images: JPG, PNG, WebP · Video: MP4, WebM, MOV",
    tip: "Models trained on firearm silhouettes perform best on side-profile shots with a visible grip and barrel.",
  },
  violence: {
    detectedClasses: "Physical fights, assaults, and aggressive multi-person interactions.",
    supportedFormats: "Images: JPG, PNG, WebP · Video: MP4, WebM, MOV (video recommended)",
    tip: "Violence is motion-dependent — short video clips usually produce a stronger signal than a single still frame.",
  },
  accident: {
    detectedClasses: "Vehicle crashes, rollovers, and collision events.",
    supportedFormats: "Images: JPG, PNG, WebP · Video: MP4, WebM, MOV",
    tip: "Include the moment of impact or the immediate aftermath; normal traffic footage should classify as clear.",
  },
};

export function TestModulePage({ module, title, description }: TestModulePageProps) {
  const content = MODULE_CONTENT[module];
  const historyKey = module as TestModuleKey;

  return (
    <>
      <PageHeader title={title} description={description} />

      <TestInfoStrip
        detectedClasses={content.detectedClasses}
        supportedFormats={content.supportedFormats}
        tip={content.tip}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ImageUploadPanel module={module} />
        <VideoUploadPanel module={module} />
      </div>

      <TestHistoryPanel module={historyKey} />
    </>
  );
}
