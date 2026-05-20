import argparse

import random

from pathlib import Path





def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument("--seed", type=int, default=0)

    parser.add_argument("--val-ratio", type=float, default=0.1)

    args = parser.parse_args()



    root = Path(__file__).resolve().parents[1]

    ds = root / "violence_dectection.yolov8"

    images_dir = ds / "train" / "images"

    if not images_dir.exists():

        raise SystemExit(f"images folder not found: {images_dir}")



    imgs = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])

    if not imgs:

        raise SystemExit("No images found")



    rnd = random.Random(int(args.seed))

    rnd.shuffle(imgs)

    val_n = max(1, int(round(len(imgs) * float(args.val_ratio))))

    val = imgs[:val_n]

    train = imgs[val_n:]



    splits_dir = root / "violence_detection" / "splits"

    splits_dir.mkdir(parents=True, exist_ok=True)

    (splits_dir / "train.txt").write_text("\n".join([str(p.resolve()) for p in train]), encoding="utf-8")
    (splits_dir / "val.txt").write_text("\n".join([str(p.resolve()) for p in val]), encoding="utf-8")
    return 0





if __name__ == "__main__":

    raise SystemExit(main())

