"""
Aplikace pro stahování nahrávek hovorů ze Spinoco API na SharePoint.

Implementuje oficiální Spinoco Call and Chat Transcription and Synchronisation API
pro stahování nahrávek za účelem trénování chatbota.

Workflow:
1. Stáhni všechny dokončené hovory s nahrávkami
2. Stáhni nahrávky (.ogg) na SharePoint do složek podle měsíce  
3. Zkontroluj velikosti souborů
4. Smaž úspěšně stažené nahrávky ze Spinoco
5. Zaloguj výsledky a ukonči se
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import structlog

from .config import settings
from .logger import setup_logging
from .spinoco_client import SpinocoClient, CallTask, CallRecording
from .sharepoint_client import SharePointClient


class SpinocoRecordingDownloader:
    """
    Jednoduchá aplikace pro batch stahování nahrávek ze Spinoco.
    
    Stáhne všechny dostupné nahrávky, nahraje na SharePoint,
    zkontroluje velikosti a smaže ze Spinoco.
    """
    
    def __init__(self):
        self.logger = setup_logging(
            log_level=settings.log_level,
            log_file="spinoco_download.log",
            enable_colors=True
        )
        
        # Jednoduché statistiky
        self.stats = {
            "calls_found": 0,
            "recordings_found": 0,
            "recordings_downloaded": 0,
            "recordings_deleted": 0,
            "errors": 0,
            "start_time": datetime.now()
        }
    
    async def run(self):
        """Hlavní metoda aplikace."""
        try:
            self.logger.info("🚀 Spouštím Spinoco Recording Downloader")
            
            # Vytvoř klienty
            async with SpinocoClient(
                api_token=settings.spinoco_api_key,
                base_url=settings.spinoco_base_url
            ) as spinoco_client:
    
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
    
    async with sharepoint_client:
                
                self.logger.info("✅ Klienti úspěšně inicializováni")
                
                # Spusť batch processing
                await self.process_all_recordings(spinoco_client, sharepoint_client)
                
                # Výsledné statistiky
                self.log_final_stats()
                
        except KeyboardInterrupt:
            self.logger.info("⏹️ Stahování přerušeno uživatelem")
        except Exception as e:
            self.logger.error("❌ Kritická chyba aplikace", error=str(e))
            self.stats["errors"] += 1
            raise
    
    async def process_all_recordings(self, spinoco_client: SpinocoClient, sharepoint_client: SharePointClient):
        """
        Hlavní batch processing logika.
        
        1. Získej všechny dokončené hovory s nahrávkami
        2. Stáhni všechny nahrávky na SharePoint
        3. Zkontroluj velikosti
        4. Smaž úspěšné ze Spinoco
        """
        self.logger.info("📞 Získávám všechny dokončené hovory s nahrávkami")
        
        # Krok 1: Získej všechny hovory s nahrávkami
        calls_with_recordings = []
        async for call in spinoco_client.get_completed_calls_with_recordings():
            calls_with_recordings.append(call)
            self.stats["calls_found"] += 1
            
            # Spočítej nahrávky
            recordings = spinoco_client.extract_available_recordings(call)
            self.stats["recordings_found"] += len(recordings)
        
        self.logger.info(
            f"🔍 Nalezeno {self.stats['calls_found']} hovorů "
            f"s {self.stats['recordings_found']} nahrávkami"
        )
        
        if not calls_with_recordings:
            self.logger.info("✅ Žádné nové nahrávky k stažení")
            return
        
        # Krok 2: Stáhni všechny nahrávky na SharePoint
        download_results = []
        semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        
        download_tasks = []
        for call in calls_with_recordings:
            recordings = spinoco_client.extract_available_recordings(call)
            for recording in recordings:
                task = self.download_single_recording(
                    call, recording, spinoco_client, sharepoint_client, semaphore
                )
                download_tasks.append(task)
        
        # Spusť paralelně
        self.logger.info(f"⬇️ Stahuji {len(download_tasks)} nahrávek paralelně")
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        # Krok 3: Zpracuj výsledky a smaž úspěšné ze Spinoco
        successful_deletions = []
        for i, result in enumerate(download_results):
            if isinstance(result, Exception):
                self.logger.error(f"❌ Chyba při stahování: {result}")
                self.stats["errors"] += 1
            else:
                call, recording, success = result
                if success:
                    self.stats["recordings_downloaded"] += 1
                    successful_deletions.append((call, recording))
                else:
                    self.stats["errors"] += 1
        
        # Krok 4: Smaž úspěšně stažené nahrávky ze Spinoco
        if successful_deletions:
            self.logger.info(f"🗑️ Mažu {len(successful_deletions)} nahrávek ze Spinoco")
            await self.delete_recordings_from_spinoco(
                successful_deletions, spinoco_client
            )
        
        self.logger.info("✅ Batch processing dokončen")
    
    async def download_single_recording(
        self,
        call: CallTask,
        recording: CallRecording,
        spinoco_client: SpinocoClient,
        sharepoint_client: SharePointClient,
        semaphore: asyncio.Semaphore
    ) -> tuple[CallTask, CallRecording, bool]:
        """
        Stáhne jednu nahrávku ze Spinoco na SharePoint a zkontroluje velikost.
        
        Returns:
            tuple: (call, recording, success)
        """
        async with semaphore:
            try:
                # Vygeneruj název souboru podle metadat (max 15 slov)
                filename = self.generate_filename_from_metadata(call, recording)
                
                # Určí složku podle měsíce
                folder_path = self.get_month_folder_path(call)
                
                self.logger.info(
                    f"⬇️ Stahuji nahrávku {recording.id}",
                    call_id=call.id,
                    filename=filename,
                    folder=folder_path
                )
                
                # Stáhni nahrávku ze Spinoco
                recording_data = await spinoco_client.download_recording(call.id, recording.id)
                original_size = len(recording_data)
                
                # Nahraj na SharePoint
                file_info = await sharepoint_client.upload_file(
                    file_content=recording_data,
                    filename=filename,
                    folder_path=folder_path,
                    overwrite=False
                )
                
                # Zkontroluj velikost
                uploaded_size = file_info.get("size", 0)
                if uploaded_size != original_size:
                    self.logger.error(
                        f"❌ Velikost se neshoduje: {original_size} != {uploaded_size}",
                        filename=filename
                    )
                    return call, recording, False
                
                self.logger.info(
                    f"✅ Nahrávka úspěšně nahrána a zkontrolována",
                    filename=filename,
                    size_mb=round(original_size / 1024 / 1024, 2)
                )
                
                return call, recording, True
                
            except Exception as e:
                self.logger.error(
                    f"❌ Chyba při stahování nahrávky",
                    call_id=call.id,
                    recording_id=recording.id,
                    error=str(e)
                )
                return call, recording, False
    
    async def delete_recordings_from_spinoco(
        self,
        successful_deletions: List[tuple[CallTask, CallRecording]],
        spinoco_client: SpinocoClient
    ):
        """Smaže úspěšně stažené nahrávky ze Spinoco."""
        
        delete_tasks = []
        for call, recording in successful_deletions:
            delete_task = spinoco_client.delete_recording(call.id, recording.id)
            delete_tasks.append(delete_task)
        
        # Smaž paralelně
        delete_results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        
        # Zpracuj výsledky
        for i, result in enumerate(delete_results):
            call, recording = successful_deletions[i]
            if isinstance(result, Exception):
                self.logger.error(
                    f"❌ Nepodařilo se smazat nahrávku ze Spinoco",
                    call_id=call.id,
                    recording_id=recording.id,
                    error=str(result)
                )
                self.stats["errors"] += 1
            else:
                self.stats["recordings_deleted"] += 1
                self.logger.debug(
                    f"🗑️ Nahrávka smazána ze Spinoco",
                    call_id=call.id,
                    recording_id=recording.id
                )
    
    def generate_filename_from_metadata(self, call: CallTask, recording: CallRecording) -> str:
        """
        Vygeneruje název souboru z metadat hovoru (max 15 slov).
        
        Formát: YYYYMMDD_HHMMSS_caller_callee.ogg
        """
        try:
            # Datum z lastUpdate
            call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
            date_str = call_time.strftime("%Y%m%d_%H%M%S")
            
            # Telefonní čísla (zkrácené)
            caller, callee = self.extract_phone_numbers(call)
            caller_short = caller[-6:] if caller else "unknown"
            callee_short = callee[-6:] if callee else "unknown" 
            
            # Sestavit název (max 15 slov = cca 60 znaků)
            filename = f"{date_str}_{caller_short}_{callee_short}_{recording.id[:8]}.ogg"
            
            # Ořízni na rozumnou délku
            if len(filename) > 60:
                filename = f"{date_str}_{recording.id[:8]}.ogg"
            
            return filename
            
        except Exception as e:
            self.logger.warning(f"Chyba při generování názvu souboru: {e}")
            # Fallback
            return f"{call.id}_{recording.id}.ogg"
    
    def get_month_folder_path(self, call: CallTask) -> str:
        """Vrátí cestu ke složce podle měsíce z lastUpdate."""
        try:
            call_time = datetime.fromtimestamp(call.lastUpdate / 1000)
            month_folder = call_time.strftime("%Y/%m")
            
            # Kombinuj s base folder path
            if settings.sharepoint_folder_path:
                return f"{settings.sharepoint_folder_path.strip('/')}/{month_folder}"
            else:
                return month_folder
                
        except Exception as e:
            self.logger.warning(f"Chyba při určování složky: {e}")
            return settings.sharepoint_folder_path or "recordings"
    
    def extract_phone_numbers(self, call: CallTask) -> tuple[str, str]:
        """Extrahuje telefonní čísla z call task."""
        try:
            direction = call.tpe.get("direction", {})
            direction_type = direction.get("__tpe")
            
            if direction_type == "Terminating":
                # Příchozí hovor
                caller = direction.get("from", {}).get("number", {}).get("e164", "")
                callee = direction.get("toPhoneNumber", "")
            elif direction_type == "Originating":
                # Odchozí hovor
                caller = direction.get("fromPhoneNumber", "")
                callee = direction.get("to", {}).get("number", {}).get("e164", "")
            else:
                return "", ""
            
            return caller.lstrip('+'), callee.lstrip('+')
            
        except Exception:
            return "", ""
    
    def log_final_stats(self):
        """Vypíše finální statistiky."""
        duration = datetime.now() - self.stats["start_time"]
        
        self.logger.info(
            "📊 Finální statistiky stahování",
            duration=str(duration),
            calls_found=self.stats["calls_found"],
            recordings_found=self.stats["recordings_found"],
            recordings_downloaded=self.stats["recordings_downloaded"],
            recordings_deleted=self.stats["recordings_deleted"],
            errors=self.stats["errors"]
        )
        
        if self.stats["errors"] > 0:
            self.logger.warning(f"⚠️ Dokončeno s {self.stats['errors']} chybami")
        else:
            self.logger.info("🎉 Všechny nahrávky úspěšně zpracovány!")


async def main():
    """Hlavní entry point aplikace."""
    try:
        downloader = SpinocoRecordingDownloader()
        await downloader.run()
        return 0
    except Exception as e:
        print(f"❌ Kritická chyba: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
