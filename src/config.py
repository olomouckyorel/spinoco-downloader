"""
Konfigurace pro Spinoco Recording Downloader
"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Nastavení pro Spinoco Recording Downloader"""
    
    # Spinoco API Configuration
    spinoco_api_key: str
    spinoco_base_url: str = "https://api.spinoco.com"
    spinoco_account_id: str
    
    # SharePoint OAuth2 Configuration
    sharepoint_site_url: str
    sharepoint_client_id: Optional[str] = None
    sharepoint_client_secret: Optional[str] = None
    sharepoint_tenant_id: Optional[str] = None
    sharepoint_folder_path: str = "/Shared Documents/Spinoco Calls"
    
    # Legacy SharePoint credentials
    sharepoint_username: Optional[str] = None
    sharepoint_password: Optional[str] = None
    
    # Application Settings
    log_level: str = "INFO"
    log_file: Path = Path("./logs/spinoco_download.log")
    max_concurrent_downloads: int = 5
    download_batch_size: int = 100
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    
    # File Processing
    supported_formats: str = "ogg"
    max_file_size_mb: int = 100
    temp_download_path: Path = Path("./temp_downloads")
    
    # Test Mode
    test_mode: bool = True
    max_test_recordings: int = 5
    local_download_path: Path = Path("./test_recordings")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    def use_oauth2(self) -> bool:
        """Zkontroluje, zda máme OAuth2 credentials"""
        return all([
            self.sharepoint_client_id,
            self.sharepoint_client_secret,
            self.sharepoint_tenant_id
        ])
        
    def __post_init__(self):
        """Zajistí vytvoření potřebných adresářů"""
        self.temp_download_path.mkdir(parents=True, exist_ok=True)
        self.local_download_path.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


# Globální instance nastavení
settings = Settings()