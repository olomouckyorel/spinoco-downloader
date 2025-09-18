#!/usr/bin/env python3
"""
Test jen Spinoco API - zobrazí hovory s nahrávkami bez stahování.
"""

import asyncio
import sys
from pathlib import Path

# Přidej src do PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.spinoco_client import SpinocoClient


async def main():
    print("🔍 Testuji jen Spinoco API - zobrazím hovory s nahrávkami")
    
    async with SpinocoClient(
        api_token=settings.spinoco_api_key,
        base_url=settings.spinoco_base_url
    ) as client:
        
        count = 0
        total_recordings = 0
        
        async for call in client.get_completed_calls_with_recordings():
            recordings = client.extract_available_recordings(call)
            
            print(f"📞 Hovor {call.id}")
            print(f"   Nahrávek: {len(recordings)}")
            print(f"   Datum: {call.lastUpdate}")
            
            for recording in recordings:
                print(f"   - Nahrávka {recording.id}: {recording.duration}ms")
            
            count += 1
            total_recordings += len(recordings)
            
            if count >= 10:  # Jen prvních 10
                break
        
        print(f"\n📊 Celkem: {count} hovorů, {total_recordings} nahrávek")
        print("✅ Spinoco API funguje perfektně!")


if __name__ == "__main__":
    asyncio.run(main())
