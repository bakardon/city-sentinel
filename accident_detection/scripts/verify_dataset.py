import os
from pathlib import Path
from typing import Dict, List, Tuple


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _count_images(folder: Path) -> int:
    if not folder.exists() or not folder.is_dir():
        return 0
    count = 0
    for root, _, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() in IMAGE_EXTS:
                count += 1
    return count


def _check_split(base: Path, split: str, classes: List[str]) -> Tuple[Dict[str, int], List[str]]:
    counts: Dict[str, int] = {}
    issues: List[str] = []
    split_dir = base / split
    if not split_dir.exists():
        issues.append(f"Missing split folder: {split_dir}")
        return counts, issues

    for cls in classes:
        cls_dir = split_dir / cls
        if not cls_dir.exists():
            issues.append(f"Missing class folder: {cls_dir}")
            counts[cls] = 0
            continue
        n = _count_images(cls_dir)
        counts[cls] = n
        if n == 0:
            issues.append(f"Empty class folder: {cls_dir}")

    return counts, issues


def verify_yolo_classification_dataset(data_root: Path) -> int:
    classes = ["accident", "non-accident"]
    splits = ["train", "val"]

    print(f"Dataset root: {data_root}")
    print(f"Expected structure: train/<class>, val/<class>")
    print(f"Classes: {', '.join(classes)}")
    print("")

    all_issues: List[str] = []
    summary: Dict[str, Dict[str, int]] = {}

    for split in splits:
        counts, issues = _check_split(data_root, split, classes)
        summary[split] = counts
        all_issues.extend(issues)

    print("Counts:")
    for split in splits:
        counts = summary.get(split, {})
        for cls in classes:
            print(f"  {split}/{cls}: {counts.get(cls, 0)}")
    print("")

    train_total = sum(summary.get("train", {}).values())
    val_total = sum(summary.get("val", {}).values())

    print(f"Totals: train={train_total}, val={val_total}")
    print("")

    ready = True
    if all_issues:
        ready = False
        print("Issues:")
        for issue in all_issues:
            print(f"  - {issue}")
        print("")

    if train_total == 0 or val_total == 0:
        ready = False
        print("Issues:")
        if train_total == 0:
            print("  - Train split has 0 images")
        if val_total == 0:
            print("  - Val split has 0 images")
        print("")

    if ready:
        print("YOLO classification readiness: READY")
        print("Suggested train command:")
        print("  yolo classify train data=<data_root> model=yolov8n-cls.pt imgsz=224 epochs=50 device=0")
        return 0

    print("YOLO classification readiness: NOT READY")
    return 2


if __name__ == "__main__":
    default_root = Path(r"D:\hanan_fyp\accident_detection\data")
    raise SystemExit(verify_yolo_classification_dataset(default_root))

