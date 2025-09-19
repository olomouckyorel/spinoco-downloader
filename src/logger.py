"""
Structured logging for Spinoco Whisper Transcriber

Provides consistent logging across the application with support for both
JSON and human-readable formats.
"""

import sys
import logging
from typing import Any, Dict, Optional
from pathlib import Path
import structlog
from structlog.types import FilteringBoundLogger


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[Path] = None
) -> FilteringBoundLogger:
    """
    Setup structured logging configuration
    
    Args:
        level: Logging level (DEBUG/INFO/WARNING/ERROR)
        format_type: Format type (json/text)
        log_file: Optional file to write logs to
        
    Returns:
        Configured structlog logger
    """
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )
    
    # Processors for structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add appropriate renderer based on format
    if format_type.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback
            )
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Create logger
    logger = structlog.get_logger()
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        
        if format_type.lower() == "json":
            file_handler.setFormatter(
                logging.Formatter('%(message)s')
            )
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
        
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "whisper") -> FilteringBoundLogger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


class TranscriptionLogger:
    """Specialized logger for transcription operations"""
    
    def __init__(self, logger: Optional[FilteringBoundLogger] = None):
        self.logger = logger or get_logger("transcription")
    
    def transcription_started(self, filename: str, model: str, device: str) -> None:
        """Log transcription start"""
        self.logger.info(
            "🎤 Transcription started",
            filename=filename,
            model=model,
            device=device
        )
    
    def transcription_completed(
        self,
        filename: str,
        duration: float,
        word_count: int,
        processing_time: float,
        avg_confidence: float
    ) -> None:
        """Log successful transcription completion"""
        self.logger.info(
            "✅ Transcription completed",
            filename=filename,
            duration_seconds=duration,
            word_count=word_count,
            processing_time_seconds=processing_time,
            avg_confidence=avg_confidence,
            real_time_factor=round(processing_time / duration, 2) if duration > 0 else 0
        )
    
    def transcription_failed(self, filename: str, error: str) -> None:
        """Log transcription failure"""
        self.logger.error(
            "❌ Transcription failed",
            filename=filename,
            error=error
        )
    
    def batch_started(self, total_files: int) -> None:
        """Log batch processing start"""
        self.logger.info(
            "🚀 Batch transcription started",
            total_files=total_files
        )
    
    def batch_progress(self, current: int, total: int, filename: str) -> None:
        """Log batch progress"""
        progress = round((current / total) * 100, 1)
        self.logger.info(
            f"📊 Progress {current}/{total} ({progress}%)",
            filename=filename,
            progress_percent=progress
        )
    
    def batch_completed(
        self,
        processed: int,
        failed: int,
        skipped: int,
        total_time: float
    ) -> None:
        """Log batch completion"""
        self.logger.info(
            "🎉 Batch transcription completed",
            processed=processed,
            failed=failed,
            skipped=skipped,
            total_time_seconds=total_time,
            success_rate=round((processed / (processed + failed)) * 100, 1) if (processed + failed) > 0 else 0
        )
    
    def model_loaded(self, model: str, device: str, load_time: float) -> None:
        """Log model loading"""
        self.logger.info(
            "🧠 Whisper model loaded",
            model=model,
            device=device,
            load_time_seconds=load_time
        )
    
    def model_load_failed(self, model: str, error: str) -> None:
        """Log model loading failure"""
        self.logger.error(
            "❌ Failed to load Whisper model",
            model=model,
            error=error
        )
    
    def file_skipped(self, filename: str, reason: str) -> None:
        """Log file skipping"""
        self.logger.info(
            "⏭️ File skipped",
            filename=filename,
            reason=reason
        )
    
    def quality_warning(self, filename: str, avg_confidence: float, threshold: float) -> None:
        """Log quality warning"""
        self.logger.warning(
            "⚠️ Low transcription confidence",
            filename=filename,
            avg_confidence=avg_confidence,
            threshold=threshold
        )
    
    def watch_mode_started(self, directory: str, interval: int) -> None:
        """Log watch mode start"""
        self.logger.info(
            "👁️ Watch mode started",
            directory=directory,
            scan_interval_seconds=interval
        )
    
    def new_file_detected(self, filename: str) -> None:
        """Log new file detection in watch mode"""
        self.logger.info(
            "🆕 New file detected",
            filename=filename
        )