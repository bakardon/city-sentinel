import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_device(device: str) -> str:
    try:
        import torch

        if str(device).strip().lower() in {"", "auto"}:
            return "0" if torch.cuda.is_available() else "cpu"
    except Exception:
        pass
    return str(device or "auto")


def _load_fire_config():
    src = PROJECT_ROOT / "fire_detection" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    import config as fire_config

    return fire_config


def _load_accident_config():
    src = PROJECT_ROOT / "accident_detection" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    import config as acc_config

    return acc_config


def _load_file_module(mod_name: str, file_path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_info(module_name: str):
    if module_name == "fire":
        cfg = _load_fire_config()
        return ("FIRE", "detect", cfg.resolve_weights_path(), int(cfg.IMGSZ))
    if module_name == "knife":
        cfg = _load_file_module("knife_export_config", PROJECT_ROOT / "knife_detection" / "src" / "config.py")
        return ("KNIFE", "detect", cfg.resolve_weights_path(), int(cfg.IMGSZ))
    if module_name == "weapon":
        cfg = _load_file_module("weapon_export_config", PROJECT_ROOT / "weapon_detection" / "src" / "config.py")
        return ("WEAPON", "detect", cfg.resolve_weights_path(), int(cfg.IMGSZ))
    if module_name == "violence":
        cfg = _load_file_module("violence_export_config", PROJECT_ROOT / "violence_detection" / "src" / "config.py")
        return ("VIOLENCE", "detect", cfg.resolve_weights_path(), int(cfg.IMGSZ))
    if module_name == "accident":
        cfg = _load_accident_config()
        weights = str(os.getenv("ACCIDENT_WEIGHTS_PATH") or cfg.DEFAULT_WEIGHTS)
        return ("ACCIDENT", "classify", weights, int(getattr(cfg, "IMGSZ", 640)))
    raise ValueError(f"Unsupported module: {module_name}")


def export_module(module_name: str, fmt: str, device: str, half: bool, dynamic: bool, batch: int, workspace: float | None):
    from ultralytics import YOLO

    prefix, task, weights_path, imgsz = _module_info(module_name)
    weights = Path(weights_path)
    if not weights.exists() and weights.suffix != ".pt":
        raise FileNotFoundError(f"{module_name}: weights not found: {weights}")

    print(f"[{module_name}] prefix={prefix} task={task} weights={weights_path} imgsz={imgsz} device={device} format={fmt}")
    model = YOLO(str(weights_path), task=task)
    kwargs = {
        "format": fmt,
        "imgsz": imgsz,
        "device": device,
        "half": bool(half),
        "batch": int(batch),
    }
    if fmt == "engine":
        kwargs["dynamic"] = bool(dynamic)
        if workspace is not None:
            kwargs["workspace"] = float(workspace)
    out = model.export(**kwargs)
    print(f"[{module_name}] exported -> {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export project YOLO models to TensorRT engines or ONNX.")
    parser.add_argument(
        "--modules",
        nargs="+",
        default=["fire", "knife", "weapon", "violence", "accident"],
        choices=["fire", "knife", "weapon", "violence", "accident"],
    )
    parser.add_argument("--format", default="engine", choices=["engine", "onnx"])
    parser.add_argument("--device", default="auto")
    parser.add_argument("--half", action="store_true", default=True)
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--workspace", type=float, default=None)
    args = parser.parse_args()

    device = _resolve_device(args.device)
    for module_name in args.modules:
        try:
            export_module(
                module_name=module_name,
                fmt=args.format,
                device=device,
                half=bool(args.half),
                dynamic=bool(args.dynamic),
                batch=int(args.batch),
                workspace=args.workspace,
            )
        except Exception as e:
            print(f"[{module_name}] export failed: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
