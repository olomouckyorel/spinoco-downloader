"""
Spinoco Whisper Transcriber
High-quality speech-to-text transcription module
"""

from .transcriber import TranscriberModule
from .config import settings
from .logger import logger

__version__ = "1.0.0"
__all__ = ["TranscriberModule", "settings", "logger"]
