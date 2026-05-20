import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple

from ultralytics import YOLO


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--weights",
        default=r"D:\hanan_fyp\accident_detection\outputs\accident_cls\weights\best.pt",
        help="Path to trained classification weights (best.pt).",
    )
    p.add_argument("--folder", required=True, help="Folder containing images (recursively).")
    p.add_argument(
        "--outdir",
        default=r"D:\hanan_fyp\accident_detection\outputs\predictions",
        help="Directory to save prediction outputs.",
    )
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--device", default="0")
    p.add_argument("--max", type=int, default=0, help="Optional limit on number of images to process (0 = all).")
    return p.parse_args()


def iter_images(folder: Path) -> Iterable[Path]:
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in IMAGE_EXTS:
            yield path


def get_top1(result) -> Tuple[str, float]:
    probs = result.probs
    if probs is None:
        return "unknown", 0.0
    idx = int(probs.top1)
    conf = float(probs.top1conf)
    name = result.names.get(idx, str(idx))
    return str(name), conf


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


def main() -> None:
    args = parse_args()
    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")

    outdir = Path(args.outdir)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = outdir / f"batch_{run_id}"
    copies_dir = run_dir / "files"
    run_dir.mkdir(parents=True, exist_ok=True)
    copies_dir.mkdir(parents=True, exist_ok=True)

    images = list(iter_images(folder))
    if args.max and args.max > 0:
        images = images[: args.max]

    if not images:
        raise SystemExit("No images found to process.")

    model = YOLO(args.weights)
    csv_path = run_dir / "predictions.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source_path", "copied_path", "predicted_class", "confidence"])

        for img_path in images:
            results = model.predict(
                source=str(img_path),
                imgsz=args.imgsz,
                device=args.device,
                verbose=False,
            )
            result = results[0]
            pred_class, conf = get_top1(result)

            print(f"{img_path} -> {pred_class} ({conf:.4f})")

            rel = safe_name(str(img_path.relative_to(folder)).replace("\\", "__").replace("/", "__"))
            copied_name = f"{Path(rel).stem}__{pred_class}__{conf:.4f}{img_path.suffix}"
            copied_path = copies_dir / copied_name
            shutil.copy2(img_path, copied_path)

            writer.writerow([str(img_path), str(copied_path), pred_class, f"{conf:.6f}"])

    print(f"Saved CSV: {csv_path}")
    print(f"Saved files: {copies_dir}")


if __name__ == "__main__":
    main()

