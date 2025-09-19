"""
Configuration management for Spinoco Whisper Transcriber

Handles environment variables and application settings.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Whisper Model Settings
    whisper_model: str = Field(
        default="large-v3",
        description="Whisper model to use (tiny/base/small/medium/large/large-v3)"
    )
    
    whisper_device: str = Field(
        default="auto",
        description="Device for Whisper (auto/cpu/cuda)"
    )
    
    whisper_language: str = Field(
        default="cs",
        description="Language code for transcription"
    )
    
    # Processing Settings
    batch_size: int = Field(
        default=1,
        description="Number of files to process simultaneously"
    )
    
    enable_gpu: bool = Field(
        default=True,
        description="Enable GPU acceleration if available"
    )
    
    temperature: float = Field(
        default=0.0,
        description="Whisper temperature (0.0 = deterministic)"
    )
    
    beam_size: int = Field(
        default=5,
        description="Beam search size (1-5, higher = better quality)"
    )
    
    best_of: int = Field(
        default=5,
        description="Number of candidates to try (1-5)"
    )
    
    # Directory Configuration
    input_dir: str = Field(
        default="data/input",
        description="Directory containing .ogg files to transcribe"
    )
    
    output_dir: str = Field(
        default="data/output", 
        description="Directory for .txt transcript outputs"
    )
    
    metadata_dir: str = Field(
        default="data/metadata",
        description="Directory for .json metadata files"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR)"
    )
    
    log_format: str = Field(
        default="json",
        description="Log format (json/text)"
    )
    
    # Technical Support Optimization
    technical_prompt: bool = Field(
        default=True,
        description="Use technical support optimized prompts"
    )
    
    initial_prompt: str = Field(
        default="Toto je nahrávka technické podpory pro kotle a topení. Obsahuje technické termíny, kódy chyb a návody na opravu.",
        description="Initial prompt for Whisper to improve technical transcription"
    )
    
    # File Processing
    skip_existing: bool = Field(
        default=True,
        description="Skip files that already have transcripts"
    )
    
    # Watch Mode
    watch_mode: bool = Field(
        default=False,
        description="Continuously monitor input directory for new files"
    )
    
    watch_interval: int = Field(
        default=5,
        description="Seconds between directory scans in watch mode"
    )
    
    def get_input_path(self) -> Path:
        """Get input directory as Path object"""
        return Path(self.input_dir)
    
    def get_output_path(self) -> Path:
        """Get output directory as Path object"""
        return Path(self.output_dir)
    
    def get_metadata_path(self) -> Path:
        """Get metadata directory as Path object"""
        return Path(self.metadata_dir)
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist"""
        self.get_input_path().mkdir(parents=True, exist_ok=True)
        self.get_output_path().mkdir(parents=True, exist_ok=True)
        self.get_metadata_path().mkdir(parents=True, exist_ok=True)
    
    def get_whisper_device(self) -> str:
        """Determine optimal device for Whisper"""
        if self.whisper_device == "auto":
            try:
                import torch
                if torch.cuda.is_available() and self.enable_gpu:
                    return "cuda"
                else:
                    return "cpu"
            except ImportError:
                return "cpu"
        return self.whisper_device
    
    def get_whisper_config(self) -> dict:
        """Get Whisper transcription configuration"""
        config = {
            "language": self.whisper_language,
            "task": "transcribe",
            "temperature": self.temperature,
            "beam_size": self.beam_size,
            "best_of": self.best_of,
            "word_timestamps": True,
            "prepend_punctuations": "\"'"¿([{-",
            "append_punctuations": "\"'.。,，!！?？:：")]}、"
        }
        
        if self.technical_prompt:
            config["initial_prompt"] = self.initial_prompt
            
        return config


# Global settings instance
settings = Settings()