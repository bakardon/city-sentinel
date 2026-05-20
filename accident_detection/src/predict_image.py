import argparse
import cv2
from pathlib import Path
from ultralytics import YOLO
import config

def parse_args():
    parser = argparse.ArgumentParser(description="Predict Accident on a Single Image")
    parser.add_argument("--weights", default=str(config.DEFAULT_WEIGHTS), help="Path to best.pt")
    parser.add_argument("--source", required=True, help="Path to image file")
    parser.add_argument("--no_show", action="store_true")
    parser.add_argument("--out", default="", help="Optional output path to save plotted image")
    return parser.parse_args()

def main():
    args = parse_args()
    print(f"Loading model: {args.weights}")
    model = YOLO(args.weights)
    
    print(f"Predicting image: {args.source}")
    results = model.predict(args.source, imgsz=config.IMGSZ)
    
    # Process results
    for r in results:
        # Create a displayable image with labels
        im_bgr = r.plot()
        
        # Output Top-1 Prediction
        top1_idx = int(r.probs.top1)
        top1_conf = float(r.probs.top1conf)
        top1_name = r.names[top1_idx]
        print(f"Prediction: {top1_name.upper()} (Confidence: {top1_conf:.3f})")

        out_path = None
        if args.out:
            out_path = Path(args.out)
        elif args.no_show:
            out_dir = Path(config.OUTPUTS_DIR) / "predict_image"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(args.source).stem
            out_path = out_dir / f"{stem}__pred.jpg"
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_path), im_bgr)
            print(f"Saved: {out_path}")

        if not args.no_show:
            cv2.imshow("Accident Classification", im_bgr)

    if not args.no_show:
        print("Press any key to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
