"""
Konfigurace pro Spinoco Whisper Transcriber
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Nastavení pro Whisper transcriber"""
    
    # Whisper model configuration
    whisper_model: str = "large-v3"
    whisper_language: str = "czech"
    whisper_device: str = "auto"  # auto, cpu, cuda
    
    # File paths
    input_folder: Path = Path("../downloaded_recordings")
    output_folder: Path = Path("./data/transcriptions")
    processed_folder: Path = Path("./data/processed")
    
    # Processing settings
    batch_size: int = 1
    max_concurrent_jobs: int = 2
    audio_chunk_length: int = 30  # seconds
    
    # Whisper quality settings
    whisper_temperature: float = 0.0
    whisper_best_of: int = 5
    whisper_beam_size: int = 5
    condition_on_previous_text: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("./logs/transcriber.log")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    def __post_init__(self):
        """Zajistí vytvoření potřebných adresářů"""
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


# Globální instance nastavení
settings = Settings()
