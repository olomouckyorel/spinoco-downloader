#!/usr/bin/env python3
"""
DEMO verze Spinoco Download aplikace pro ověření Denisem.

Připojí se k Spinoco API, zobrazí všechny hovory s nahrávkami,
ale nestahuje skutečně - jen simuluje a ukáže co by se stáhlo.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Přidej src do PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.logger import setup_logging
from src.spinoco_client import SpinocoClient


class SpinocoDemo:
    """Demo verze pro ověření funkcionalität Denisem."""
    
    def __init__(self):
        self.logger = setup_logging(
            log_level="INFO",
            log_file="demo.log",
            enable_colors=True
        )
        
        self.stats = {
            "calls_found": 0,
            "recordings_found": 0,
            "total_size_mb": 0,
            "folders_created": set(),
            "start_time": datetime.now()
        }
    
    async def run_demo(self):
        """Spustí demo verzi aplikace."""
        self.logger.info("🚀 Spouštím DEMO verzi Spinoco Download")
        self.logger.info("📋 Tato verze NESTAHUJE soubory - jen zobrazuje co by se stáhlo")
        
        async with SpinocoClient(
            api_token=settings.spinoco_api_key,
            base_url=settings.spinoco_base_url
        ) as client:
            
            self.logger.info("✅ Připojen k Spinoco API")
            
            # Projdi hovory s nahrávkami (omezeno na 10 pro rychlost)
            count = 0
            async for call in client.get_completed_calls_with_recordings():
                await self.process_call_demo(call, client)
                count += 1
                
                # Omez na prvních 10 pro demo (rychleji)
                if count >= 10:
                    self.logger.info("⏹️ Demo omezeno na 10 hovorů pro rychlost")
                    break
            
            # Výsledný report
            self.generate_demo_report()
    
    async def process_call_demo(self, call, client):
        """Zpracuje jeden hovor v demo režimu."""
        self.stats["calls_found"] += 1
        
        # Extrahuj nahrávky
        recordings = client.extract_available_recordings(call)
        
        if not recordings:
            return
        
        # Datum hovoru
        call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
        
        self.logger.info(
            f"📞 Hovor {self.stats['calls_found']}: {call.id[:8]}...",
            datum=call_time.strftime("%Y-%m-%d %H:%M"),
            nahravek=len(recordings)
        )
        
        for recording in recordings:
            self.stats["recordings_found"] += 1
            
            # Vygeneruj název souboru (jako ve skutečné aplikaci)
            filename = self.generate_filename_demo(call, recording)
            
            # Určí složku podle měsíce
            folder_path = self.get_month_folder_demo(call)
            self.stats["folders_created"].add(folder_path)
            
            # Odhad velikosti (duration v ms -> přibližná velikost)
            size_mb = recording.duration / 1000 / 60 * 0.5  # ~0.5MB/min
            self.stats["total_size_mb"] += size_mb
            
            self.logger.info(
                f"  📁 {folder_path}/{filename}",
                velikost_mb=round(size_mb, 1),
                delka_sec=recording.duration // 1000
            )
    
    def generate_filename_demo(self, call, recording):
        """Vygeneruje název souboru (demo verze)."""
        try:
            call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
            date_str = call_time.strftime("%Y%m%d_%H%M%S")
            
            # Zkrácené ID pro čitelnost
            short_id = recording.id[:8]
            
            return f"{date_str}_nahrávka_{short_id}.ogg"
        except Exception:
            return f"hovor_{call.id[:8]}_{recording.id[:8]}.ogg"
    
    def get_month_folder_demo(self, call):
        """Vrátí cestu ke složce podle měsíce (demo)."""
        try:
            call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
            return f"Spinoco_Calls/{call_time.strftime('%Y')}/{call_time.strftime('%m')}"
        except Exception:
            return "Spinoco_Calls/Unknown"
    
    def generate_demo_report(self):
        """Vygeneruje finální report pro Denise."""
        duration = datetime.now() - self.stats["start_time"]
        
        print("\n" + "="*60)
        print("📊 DEMO REPORT - Spinoco Download Aplikace")
        print("="*60)
        print(f"⏱️  Doba běhu: {duration}")
        print(f"📞 Nalezeno hovorů: {self.stats['calls_found']}")
        print(f"🎵 Nalezeno nahrávek: {self.stats['recordings_found']}")
        print(f"💾 Celková velikost: {self.stats['total_size_mb']:.1f} MB")
        print(f"📁 Složek k vytvoření: {len(self.stats['folders_created'])}")
        print()
        print("📁 Struktura složek:")
        for folder in sorted(self.stats["folders_created"]):
            print(f"   {folder}/")
        print()
        print("✅ DEMO ÚSPĚŠNĚ DOKONČENO")
        print("🔄 Připraveno pro ověření IT a nasazení produkční verze")
        print("="*60)
        
        # Ulož report do souboru
        with open("demo_report.txt", "w", encoding="utf-8") as f:
            f.write(f"DEMO REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*50 + "\n")
            f.write(f"Nalezeno hovorů: {self.stats['calls_found']}\n")
            f.write(f"Nalezeno nahrávek: {self.stats['recordings_found']}\n")
            f.write(f"Celková velikost: {self.stats['total_size_mb']:.1f} MB\n")
            f.write(f"Složek k vytvoření: {len(self.stats['folders_created'])}\n\n")
            f.write("Struktura složek:\n")
            for folder in sorted(self.stats["folders_created"]):
                f.write(f"  {folder}/\n")
        
        print("💾 Report uložen do demo_report.txt")


async def main():
    """Hlavní entry point demo aplikace."""
    try:
        demo = SpinocoDemo()
        await demo.run_demo()
        return 0
    except Exception as e:
        print(f"❌ Chyba v demo aplikaci: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
