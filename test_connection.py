#!/usr/bin/env python3
"""
Jednoduchý test script pro ověření připojení k Spinoco API a SharePoint.
Spustí se před hlavní aplikací pro kontrolu konfigurace.
"""

import asyncio
import sys
from pathlib import Path

# Přidej src do PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.logger import setup_logging
from src.spinoco_client import SpinocoClient
from src.sharepoint_client import SharePointClient


async def test_spinoco_connection():
    """Test připojení k Spinoco API."""
    print("🔍 Testuji připojení k Spinoco API...")
    
    try:
        async with SpinocoClient(
            api_token=settings.spinoco_api_key,
            base_url=settings.spinoco_base_url
        ) as client:
            # Zkus získat labels pro ověření připojení
            skills = await client.get_skills_labels()
            print(f"✅ Spinoco API připojení OK - nalezeno {len(skills)} skills")
            
            # Test získání dokončených hovorů (jen prvních 5)
            print("🔍 Testuji získání dokončených hovorů...")
            call_count = 0
            async for call in client.get_completed_calls_with_recordings():
                call_count += 1
                if call_count >= 3:  # Jen pár pro test
                    break
            
            print(f"✅ Nalezeno {call_count} hovorů s nahrávkami")
            return True
            
    except Exception as e:
        print(f"❌ Chyba při připojení k Spinoco API: {e}")
        return False


async def test_sharepoint_connection():
    """Test připojení k SharePoint."""
    print("🔍 Testuji připojení k SharePoint...")
    
    try:
        # Vytvoř SharePoint klient s OAuth2
        if settings.use_oauth2():
            sharepoint_client = SharePointClient(
                site_url=settings.sharepoint_site_url,
                client_id=settings.sharepoint_client_id,
                client_secret=settings.sharepoint_client_secret,
                tenant_id=settings.sharepoint_tenant_id,
                folder_path=settings.sharepoint_folder_path
            )
        else:
            sharepoint_client = SharePointClient(
                site_url=settings.sharepoint_site_url,
                username=settings.sharepoint_username,
                password=settings.sharepoint_password,
                folder_path=settings.sharepoint_folder_path
            )
        
        async with sharepoint_client as client:
            # Test připojení
            await client.connect()
            print("✅ SharePoint připojení OK")
            
            # Test vytvoření složky
            await client.ensure_folder_exists(settings.sharepoint_folder_path)
            print(f"✅ Složka '{settings.sharepoint_folder_path}' je připravena")
            
            return True
            
    except Exception as e:
        print(f"❌ Chyba při připojení k SharePoint: {e}")
        return False


async def test_configuration():
    """Test konfigurace aplikace."""
    print("🔍 Testuji konfiguraci...")
    
    # Kontroluj buď OAuth2 nebo legacy credentials
    oauth2_settings = [
        'sharepoint_client_id',
        'sharepoint_client_secret', 
        'sharepoint_tenant_id'
    ]
    
    legacy_settings = [
        'sharepoint_username',
        'sharepoint_password'
    ]
    
    required_settings = [
        'spinoco_api_key',
        'spinoco_base_url', 
        'sharepoint_site_url'
    ]
    
    # Kontroluj základní nastavení
    missing = []
    for setting in required_settings:
        value = getattr(settings, setting, None)
        if not value or value.startswith('your_'):
            missing.append(setting.upper())
    
    # Kontroluj SharePoint credentials (buď OAuth2 nebo legacy)
    has_oauth2 = all(getattr(settings, setting, None) for setting in oauth2_settings)
    has_legacy = all(getattr(settings, setting, None) for setting in legacy_settings)
    
    if not has_oauth2 and not has_legacy:
        missing.extend(['SHAREPOINT_CLIENT_ID+SECRET+TENANT nebo USERNAME+PASSWORD'])
    
    if missing:
        print(f"❌ Chybějící konfigurace: {', '.join(missing)}")
        print("💡 Zkopíruj config/env.example do config/.env a vyplň správné hodnoty")
        return False
    
    print("✅ Konfigurace je kompletní")
    return True


async def main():
    """Hlavní test funkce."""
    print("🚀 Spouštím test připojení Spinoco Download aplikace")
    print("=" * 60)
    
    # Setup logging
    logger = setup_logging(log_level="INFO", enable_colors=True)
    
    # Test konfigurace
    config_ok = await test_configuration()
    if not config_ok:
        return 1
    
    print()
    
    # Test připojení
    spinoco_ok = await test_spinoco_connection()
    print()
    
    sharepoint_ok = await test_sharepoint_connection()
    print()
    
    # Výsledek
    if spinoco_ok and sharepoint_ok:
        print("🎉 Všechny testy prošly úspěšně!")
        print("💡 Můžeš spustit hlavní aplikaci: python -m src.main")
        return 0
    else:
        print("❌ Některé testy selhaly. Zkontroluj konfiguraci a připojení.")
        return 1


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\n⏹️  Test přerušen uživatelem")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Neočekávaná chyba: {e}")
        sys.exit(1)
