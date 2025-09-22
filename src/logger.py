"""
Strukturovaný logger pro Spinoco Whisper Transcriber
"""
import sys
import structlog
from pathlib import Path
from .config import settings


def setup_logger():
    """Nastavení strukturovaného loggeru"""
    
    # Zajistíme vytvoření log adresáře
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Konfigurace structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Nastavení Python logging
    import logging
    
    # File handler
    file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, settings.log_level))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level))
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return structlog.get_logger()


# Globální logger instance
logger = setup_logger()

