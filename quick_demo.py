#!/usr/bin/env python3
"""
RYCHLÁ DEMO verze - jen pár hovorů pro ukázku Denisovi.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.spinoco_client import SpinocoClient


async def quick_demo():
    print("🚀 RYCHLÁ DEMO verze Spinoco Download")
    print("📋 Ukážeme jen prvních 5 hovorů s nahrávkami")
    print("="*50)
    
    try:
        async with SpinocoClient(
            api_token=settings.spinoco_api_key,
            base_url=settings.spinoco_base_url
        ) as client:
            
            print("✅ Připojen k Spinoco API")
            
            count = 0
            total_recordings = 0
            
            async for call in client.get_completed_calls_with_recordings():
                count += 1
                
                # Extrahuj nahrávky
                recordings = client.extract_available_recordings(call)
                total_recordings += len(recordings)
                
                # Datum hovoru
                call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
                
                print(f"\n📞 Hovor {count}:")
                print(f"   ID: {call.id[:16]}...")
                print(f"   Datum: {call_time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Nahrávek: {len(recordings)}")
                
                for i, recording in enumerate(recordings, 1):
                    duration_min = recording.duration / 1000 / 60
                    size_mb = duration_min * 0.5  # odhad
                    
                    # Název souboru
                    filename = f"{call_time.strftime('%Y%m%d_%H%M%S')}_nahrávka_{recording.id[:8]}.ogg"
                    
                    # Složka podle měsíce
                    folder = f"Spinoco_Calls/{call_time.strftime('%Y/%m')}"
                    
                    print(f"   📁 {folder}/")
                    print(f"   📄 {filename}")
                    print(f"   ⏱️  Délka: {duration_min:.1f} min, Velikost: ~{size_mb:.1f} MB")
                
                # Jen 5 hovorů pro demo
                if count >= 5:
                    break
            
            print("\n" + "="*50)
            print("📊 DEMO VÝSLEDKY:")
            print(f"📞 Hovorů s nahrávkami: {count}")
            print(f"🎵 Celkem nahrávek: {total_recordings}")
            print("✅ Spinoco API funguje perfektně!")
            print("🔄 Připraveno pro ověření IT a produkční nasazení")
            print("="*50)
            
    except Exception as e:
        print(f"❌ Chyba: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(quick_demo()))
