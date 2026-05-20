import os
from ultralytics import YOLO
import config

def main():
    """
    Trains the YOLOv8 classification model on the Accident vs Non-Accident dataset.
    """
    print(f"Starting training on dataset: {config.DATA_DIR}")
    
    # Initialize the model (yolov8n-cls is the nano classification model)
    model = YOLO("yolov8n-cls.pt")
    
    # Train the model
    results = model.train(
        data=str(config.DATA_DIR),
        epochs=50,
        imgsz=config.IMGSZ,
        batch=32,
        project=str(config.OUTPUTS_DIR),
        name="accident_cls",
        exist_ok=True,
        verbose=True
    )
    
    print("\n" + "="*50)
    print("Training Complete!")
    print(f"Best model weights saved to: {results.save_dir}/weights/best.pt")
    print("="*50)

if __name__ == "__main__":
    main()
