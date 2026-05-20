import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--data",
        default=r"D:\hanan_fyp\accident_detection\data",
        help="Dataset root containing train/ and val/ folders.",
    )
    p.add_argument("--model", default="yolov8n-cls.pt", help="Ultralytics classification model.")
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch", type=int, default=-1)
    p.add_argument("--device", default="0")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--project", default=r"D:\hanan_fyp\accident_detection\outputs")
    p.add_argument("--name", default="accident_cls")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--patience", type=int, default=20)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(args.data)
    if not data_root.exists():
        raise SystemExit(f"Dataset path not found: {data_root}")

    model = YOLO(args.model)
    model.train(
        task="classify",
        data=str(data_root),
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        seed=args.seed,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()

