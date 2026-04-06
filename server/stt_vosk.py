# server/stt_vosk.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Tuple
from vosk import Model, KaldiRecognizer

# 配置模型路径 
# 默认在仓库根的 models/vosk-model-small-en-us-0.15
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "vosk-model-small-en-us-0.15"

# 允许通过环境变量覆盖
MODEL_DIR = Path(os.getenv("VOSK_MODEL_DIR", str(DEFAULT_MODEL_DIR)))

# 全局模型加载
_model: Optional[Model] = None

def ensure_model() -> Model:
    global _model
    if _model is None:
        if not MODEL_DIR.exists():
            raise RuntimeError(
                f"Vosk model directory not found: {MODEL_DIR}\n"
                f"Download and extract a model, e.g.:\n"
                f"  https://alphacephei.com/vosk/models\n"
                f"and set VOSK_MODEL_DIR or place it under {DEFAULT_MODEL_DIR}"
            )
        _model = Model(str(MODEL_DIR))
        print(f"[VOSK] model loaded: {MODEL_DIR}")
    return _model

def create_recognizer(sample_rate: int = 16000) -> KaldiRecognizer:
    """
    每个连接创建一个识别器实例
    - sample_rate: PCM16
    """
    model = ensure_model()
    rec = KaldiRecognizer(model, sample_rate)
    return rec
