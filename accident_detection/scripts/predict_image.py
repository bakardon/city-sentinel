import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

from ultralytics import YOLO


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--weights",
        default=r"D:\hanan_fyp\accident_detection\outputs\accident_cls\weights\best.pt",
        help="Path to trained classification weights (best.pt).",
    )
    p.add_argument("--image", required=True, help="Path to an input image.")
    p.add_argument(
        "--outdir",
        default=r"D:\hanan_fyp\accident_detection\outputs\predictions",
        help="Directory to save prediction outputs.",
    )
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--device", default="0")
    return p.parse_args()


def get_top1(result) -> Tuple[str, float]:
    probs = result.probs
    if probs is None:
        return "unknown", 0.0
    idx = int(probs.top1)
    conf = float(probs.top1conf)
    name = result.names.get(idx, str(idx))
    return str(name), conf


def main() -> None:
    args = parse_args()
    img_path = Path(args.image)
    if not img_path.exists() or not img_path.is_file():
        raise SystemExit(f"Image not found: {img_path}")
    if img_path.suffix.lower() not in IMAGE_EXTS:
        raise SystemExit(f"Unsupported file type: {img_path.suffix}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    results = model.predict(
        source=str(img_path),
        imgsz=args.imgsz,
        device=args.device,
        verbose=False,
    )
    result = results[0]
    pred_class, conf = get_top1(result)

    print(f"image={img_path}")
    print(f"predicted_class={pred_class}")
    print(f"confidence={conf:.4f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = img_path.stem
    copied_name = f"{stem}__{pred_class}__{conf:.4f}__{ts}{img_path.suffix}"
    copied_path = outdir / copied_name
    shutil.copy2(img_path, copied_path)

    meta_path = outdir / f"{stem}__{ts}.txt"
    meta_path.write_text(
        "\n".join(
            [
                f"image={img_path}",
                f"copied_to={copied_path}",
                f"predicted_class={pred_class}",
                f"confidence={conf:.6f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

