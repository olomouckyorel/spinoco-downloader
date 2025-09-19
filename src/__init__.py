"""
Spinoco Whisper Transcriber

High-quality audio transcription service for technical support calls
using OpenAI Whisper Large-v3 optimized for Czech language and 
heating/boiler technical terminology.
"""

__version__ = "1.0.0"
__author__ = "Spinoco AI Pipeline"
__description__ = "Standalone Whisper transcription service for technical support calls"

from .config import settings, Settings
from .logger import get_logger, setup_logging, TranscriptionLogger

__all__ = [
    "settings",
    "Settings", 
    "get_logger",
    "setup_logging",
    "TranscriptionLogger"
]