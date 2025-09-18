"""
Logging modul pro Spinoco Download aplikaci.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import structlog
from colorama import init, Fore, Style

# Inicializace colorama pro Windows
init(autoreset=True)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_colors: bool = True
) -> structlog.stdlib.BoundLogger:
    """
    Nastaví strukturované logování pro aplikaci.
    
    Args:
        log_level: Úroveň logování (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Cesta k log souboru (volitelné)
        enable_colors: Zapnout barevné logování v konzoli
    
    Returns:
        BoundLogger: Nakonfigurovaný logger
    """
    
    # Vytvoř logs složku pokud neexistuje
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Základní konfigurace
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Processors pro structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
    ]
    
    # Přidej barevný výstup pro konzoli
    if enable_colors and not log_file:
        def add_colors(logger, method_name, event_dict):
            """Přidá barvy podle úrovně logování."""
            level = event_dict.get("level", "").upper()
            colors = {
                "DEBUG": Fore.CYAN,
                "INFO": Fore.GREEN,
                "WARNING": Fore.YELLOW,
                "ERROR": Fore.RED,
                "CRITICAL": Fore.RED + Style.BRIGHT,
            }
            
            if level in colors:
                event_dict["level"] = colors[level] + level + Style.RESET_ALL
            
            return event_dict
        
        processors.append(add_colors)
    
    processors.append(structlog.dev.ConsoleRenderer())
    
    # Konfigurace structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Přidej file handler pokud je zadán log soubor
    if log_file:
        file_handler = logging.FileHandler(
            logs_dir / log_file, 
            encoding='utf-8'
        )
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    return structlog.get_logger("spinoco_download")
