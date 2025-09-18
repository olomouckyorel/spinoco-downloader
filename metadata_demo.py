#!/usr/bin/env python3
"""
Demo zobrazení metadat jednotlivých .ogg souborů ze Spinoco.
Ukáže přesně jaká data budeme mít pro každou nahrávku.
"""

import asyncio
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.spinoco_client import SpinocoClient


async def show_recording_metadata():
    """Zobrazí metadata jednotlivých nahrávek jako budou na SharePoint."""
    
    print("SPINOCO RECORDING METADATA DEMO")
    print("=" * 50)
    print("Zobrazuji metadata jednotlivých .ogg souborů")
    print()
    
    async with SpinocoClient(
        api_token=settings.spinoco_api_key,
        base_url=settings.spinoco_base_url
    ) as client:
        
        count = 0
        
        async for call in client.get_completed_calls_with_recordings():
            recordings = client.extract_available_recordings(call)
            
            for recording in recordings:
                count += 1
                
                # Datum hovoru
                call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
                
                # Telefonní čísla
                direction = call.tpe.get("direction", {})
                direction_type = direction.get("__tpe", "Unknown")
                
                if direction_type == "Terminating":
                    caller = direction.get("from", {}).get("number", {}).get("e164", "Unknown")
                    callee = direction.get("toPhoneNumber", "Unknown")
                elif direction_type == "Originating":
                    caller = direction.get("fromPhoneNumber", "Unknown")
                    callee = direction.get("to", {}).get("number", {}).get("e164", "Unknown")
                else:
                    caller = callee = "Unknown"
                
                # Název souboru
                filename = f"{call_time.strftime('%Y%m%d_%H%M%S')}_nahrávka_{recording.id[:8]}.ogg"
                
                # Složka
                folder = f"Spinoco_Calls/{call_time.strftime('%Y')}/{call_time.strftime('%m')}"
                
                # Metadata pro tento .ogg soubor
                metadata = {
                    "soubor": filename,
                    "slozka": folder,
                    "call_id": call.id,
                    "recording_id": recording.id,
                    "datum_hovoru": call_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "delka_ms": recording.duration,
                    "delka_min": round(recording.duration / 1000 / 60, 1),
                    "smer_hovoru": direction_type,
                    "volajici": caller,
                    "volany": callee,
                    "je_voicemail": recording.vm,
                    "dostupny": recording.available,
                    "ma_transkripce": len(recording.transcriptions) > 0,
                    "owner_type": call.owner.get("__tpe", "Unknown"),
                    "assignee_type": call.assignee.get("__tpe", "Unknown"),
                    "hashtags": len(call.hashTags),
                    "odhadovana_velikost_mb": round(recording.duration / 1000 / 60 * 0.5, 1)
                }
                
                print(f"=== NAHRAVKA {count} ===")
                print(f"Soubor: {folder}/{filename}")
                print(f"Call ID: {call.id}")
                print(f"Recording ID: {recording.id}")
                print(f"Datum: {metadata['datum_hovoru']}")
                print(f"Delka: {metadata['delka_min']} minut ({metadata['delka_ms']} ms)")
                print(f"Smer: {metadata['smer_hovoru']}")
                print(f"Volajici: {metadata['volajici']}")
                print(f"Volany: {metadata['volany']}")
                print(f"Voicemail: {metadata['je_voicemail']}")
                print(f"Dostupny: {metadata['dostupny']}")
                print(f"Transkripce: {metadata['ma_transkripce']}")
                print(f"Odhadovana velikost: {metadata['odhadovana_velikost_mb']} MB")
                print()
                
                # Ulož metadata do souboru (jako by bylo na SharePoint)
                metadata_filename = f"metadata_{count:03d}_{recording.id[:8]}.json"
                with open(f"demo_metadata/{metadata_filename}", "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                
                # Omez na 10 nahrávek pro demo
                if count >= 10:
                    break
            
            if count >= 10:
                break
        
        print(f"Celkem zobrazeno: {count} nahrávek")
        print(f"Metadata ulozena do: demo_metadata/")
        print("=" * 50)


async def main():
    # Vytvoř složku pro metadata
    Path("demo_metadata").mkdir(exist_ok=True)
    
    try:
        await show_recording_metadata()
        return 0
    except Exception as e:
        print(f"Chyba: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
