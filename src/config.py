"""
Konfigurační modul pro Spinoco Download aplikaci.
"""

import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Nastavení aplikace načítané z environment variables."""
    
    # Spinoco API
    spinoco_api_key: str
    spinoco_base_url: str = "https://api.spinoco.com"
    spinoco_account_id: str
    

    # SharePoint OAuth2 (preferred)
    sharepoint_site_url: str
    sharepoint_client_id: Optional[str] = None
    sharepoint_client_secret: Optional[str] = None  
    sharepoint_tenant_id: Optional[str] = None
    sharepoint_folder_path: str = "/Shared Documents/Spinoco Calls"
    
    # SharePoint Legacy (fallback)
    sharepoint_username: Optional[str] = None
    sharepoint_password: Optional[str] = None
    
    # Application settings
    log_level: str = "INFO"
    max_concurrent_downloads: int = 5
    download_batch_size: int = 100
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    
    # File processing
    supported_formats: str = "ogg"
    max_file_size_mb: int = 100
    temp_download_path: str = "./temp_downloads"
    
    @validator('supported_formats')
    def parse_supported_formats(cls, v):
        """Převede string formátů na list."""
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(',')]
        return v
    
    @validator('temp_download_path')
    def create_temp_path(cls, v):
        """Vytvoří temp složku pokud neexistuje."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    def use_oauth2(self) -> bool:
        """Zkontroluje, zda máme OAuth2 credentials."""
        return bool(
            self.sharepoint_client_id and 
            self.sharepoint_client_secret and 
            self.sharepoint_tenant_id
        )
    class Config:
        env_file = "config/.env"
        case_sensitive = False


def load_settings() -> Settings:
    """
    Načte nastavení z .env souboru.
    
    Returns:
        Settings: Objekt s načteným nastavením
    """
    # Najdi .env soubor
    env_path = Path("config/.env")
    if env_path.exists():
        load_dotenv(env_path)
    
    return Settings()


# Globální instance nastavení
settings = load_settings()
