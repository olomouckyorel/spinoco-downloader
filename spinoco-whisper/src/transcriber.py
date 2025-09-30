"""
Spinoco Whisper Transcriber
High-quality speech-to-text transcription using OpenAI Whisper Large-v3
"""
import json
import asyncio
import whisper
import torch
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import shutil

from .config import settings
from .logger import logger


class TranscriberModule:
    """
    Modul pro high-quality přepis audio souborů pomocí Whisper Large-v3
    """
    
    def __init__(self):
        self.logger = logger.bind(module="transcriber")
        self.model = None
        self._setup_device()
        
    def _setup_device(self):
        """Nastavení zařízení pro Whisper (CPU/GPU)"""
        if settings.whisper_device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = settings.whisper_device
            
        self.logger.info(f"Whisper device nastaven na: {self.device}")
        
    def _load_model(self):
        """Načtení Whisper modelu (lazy loading)"""
        if self.model is None:
            self.logger.info(f"Načítám Whisper model: {settings.whisper_model}")
            try:
                self.model = whisper.load_model(
                    settings.whisper_model, 
                    device=self.device
                )
                self.logger.info("Whisper model úspěšně načten")
            except Exception as e:
                self.logger.error(f"Chyba při načítání Whisper modelu: {e}")
                raise
                
    def _extract_metadata_from_filename(self, filename: str) -> Dict[str, Any]:
        """
        Extrahuje metadata z názvu souboru
        Format: YYYYMMDD_HHMMSS_caller_firstdigit_duration_recordingid.ogg
        """
        try:
            # Odebereme příponu
            name_without_ext = Path(filename).stem
            parts = name_without_ext.split('_')
            
            if len(parts) >= 6:
                date_str = parts[0]
                time_str = parts[1]
                caller = parts[2]
                callee_first = parts[3]
                duration = parts[4]
                recording_id = parts[5]
                
                # Parsování data a času
                datetime_str = f"{date_str}_{time_str}"
                call_datetime = datetime.strptime(datetime_str, "%Y%m%d_%H%M%S")
                
                return {
                    "call_date": call_datetime.isoformat(),
                    "caller_number": caller,
                    "callee_first_digit": callee_first,
                    "duration": duration,
                    "recording_id": recording_id,
                    "original_filename": filename
                }
            else:
                self.logger.warning(f"Neočekávaný formát názvu souboru: {filename}")
                return {"original_filename": filename}
                
        except Exception as e:
            self.logger.warning(f"Chyba při parsování názvu souboru {filename}: {e}")
            return {"original_filename": filename}
    
    def transcribe_file(self, audio_path: Path) -> Dict[str, Any]:
        """
        Přepíše jeden audio soubor pomocí Whisper
        
        Args:
            audio_path: Cesta k audio souboru
            
        Returns:
            Dict s výsledky přepisu a metadaty
        """
        self._load_model()
        
        self.logger.info(f"Začínám přepis souboru: {audio_path.name}")
        
        try:
            # Progress info
            audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"🎤 Audio: {audio_size_mb:.1f} MB, model: {settings.whisper_model}, device: {self.device}")
            
            # Whisper transcription s high-quality nastavením
            self.logger.info("⏳ Transkripce běží... (může trvat několik minut)")
            result = self.model.transcribe(
                str(audio_path),
                language="cs",  # Explicitní český kód
                temperature=settings.whisper_temperature,
                best_of=settings.whisper_best_of,
                beam_size=settings.whisper_beam_size,
                condition_on_previous_text=settings.condition_on_previous_text,
                initial_prompt="Toto je nahrávka technické podpory v češtině. Obsahuje konverzaci o kotlích, topení a technických problémech.",
                verbose=True  # Zobrazit progress
            )
            
            # Extrakce metadat z názvu souboru
            file_metadata = self._extract_metadata_from_filename(audio_path.name)
            
            # Sestavení výsledku
            transcription_result = {
                "transcription": {
                    "text": result["text"].strip(),
                    "language": result["language"],
                    "segments": result["segments"]
                },
                "metadata": {
                    **file_metadata,
                    "transcribed_at": datetime.now().isoformat(),
                    "whisper_model": settings.whisper_model,
                    "audio_file_size": audio_path.stat().st_size,
                    "audio_file_path": str(audio_path)
                },
                "processing_info": {
                    "device_used": self.device,
                    "whisper_settings": {
                        "temperature": settings.whisper_temperature,
                        "best_of": settings.whisper_best_of,
                        "beam_size": settings.whisper_beam_size,
                        "condition_on_previous_text": settings.condition_on_previous_text
                    }
                }
            }
            
            self.logger.info(
                f"Přepis dokončen: {audio_path.name}",
                text_length=len(result["text"]),
                segments_count=len(result["segments"])
            )
            
            return transcription_result
            
        except Exception as e:
            self.logger.error(f"Chyba při přepisu souboru {audio_path.name}: {e}")
            raise
    
    def save_transcription(self, transcription_result: Dict[str, Any], output_path: Path):
        """Uloží výsledek přepisu do JSON souboru"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(transcription_result, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Přepis uložen: {output_path}")
            
        except Exception as e:
            self.logger.error(f"Chyba při ukládání přepisu {output_path}: {e}")
            raise
    
    def move_processed_file(self, source_path: Path, processed_folder: Path):
        """Přesune zpracovaný audio soubor do processed složky"""
        try:
            processed_folder.mkdir(parents=True, exist_ok=True)
            dest_path = processed_folder / source_path.name
            shutil.move(str(source_path), str(dest_path))
            
            self.logger.info(f"Soubor přesunut: {source_path.name} -> processed/")
            
        except Exception as e:
            self.logger.error(f"Chyba při přesunu souboru {source_path.name}: {e}")
            raise
    
    def process_file(self, audio_path: Path) -> bool:
        """
        Zpracuje jeden audio soubor - přepíše a uloží výsledek
        
        Returns:
            True pokud bylo zpracování úspěšné
        """
        try:
            # Transcription
            transcription_result = self.transcribe_file(audio_path)
            
            # Výstupní soubor
            output_filename = f"{audio_path.stem}_transcription.json"
            output_path = settings.output_folder / output_filename
            
            # Uložení
            self.save_transcription(transcription_result, output_path)
            
            # Přesun zpracovaného souboru
            self.move_processed_file(audio_path, settings.processed_folder)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Chyba při zpracování souboru {audio_path.name}: {e}")
            return False
    
    def get_pending_files(self) -> List[Path]:
        """Najde všechny audio soubory čekající na zpracování"""
        audio_extensions = ['.ogg', '.wav', '.mp3', '.m4a', '.flac']
        pending_files = []
        
        if settings.input_folder.exists():
            for ext in audio_extensions:
                pending_files.extend(settings.input_folder.glob(f"*{ext}"))
        
        self.logger.info(f"Nalezeno {len(pending_files)} souborů k zpracování")
        return pending_files
    
    async def process_all_pending(self) -> Dict[str, int]:
        """
        Zpracuje všechny čekající audio soubory
        
        Returns:
            Dict se statistikami zpracování
        """
        pending_files = self.get_pending_files()
        
        if not pending_files:
            self.logger.info("Žádné soubory k zpracování")
            return {"processed": 0, "failed": 0, "total": 0}
        
        stats = {"processed": 0, "failed": 0, "total": len(pending_files)}
        
        self.logger.info(f"Začínám zpracování {len(pending_files)} souborů")
        
        for audio_file in pending_files:
            try:
                success = self.process_file(audio_file)
                if success:
                    stats["processed"] += 1
                else:
                    stats["failed"] += 1
                    
            except Exception as e:
                self.logger.error(f"Neočekávaná chyba při zpracování {audio_file.name}: {e}")
                stats["failed"] += 1
        
        self.logger.info(
            "Zpracování dokončeno",
            **stats
        )
        
        return stats


async def main():
    """Hlavní funkce pro spuštění transcriberu"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Spinoco Whisper Transcriber")
    parser.add_argument('--input', type=str, help='Cesta k jednomu audio souboru (worker mode)')
    parser.add_argument('--output', type=str, help='Výstupní adresář pro transkripty (worker mode)')
    parser.add_argument('--no-move', action='store_true', 
                       help='Nepřesouvat zpracované soubory (pro pipeline/worker mode)')
    args = parser.parse_args()
    
    transcriber = TranscriberModule()
    
    if args.input and args.output:
        # WORKER MODE: Zpracování jednoho souboru pro pipeline
        input_path = Path(args.input)
        output_dir = Path(args.output)
        
        if not input_path.exists():
            transcriber.logger.error(f"Audio soubor neexistuje: {input_path}")
            print(f"CHYBA: Audio soubor neexistuje: {input_path}")
            sys.exit(1)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Zpracuj jeden soubor
            transcriber.logger.info(f"Worker mode: Zpracovávám {input_path.name}")
            result = transcriber.transcribe_file(input_path)
            
            # Ulož výsledek pomocí save_transcription metody
            output_file = output_dir / f"{input_path.stem}_transcription.json"
            transcriber.save_transcription(result, output_file)
            
            transcriber.logger.info(f"Worker mode: Úspěšně zpracováno {input_path.name}")
            print(f"Uspesne zpracovano: {input_path.name}")
            print(f"Vystup: {output_file}")
            
            # V worker mode NEPŘESOUVAT soubor (zůstává v source)
            if not args.no_move:
                transcriber.logger.info("Standalone mode: Přesouvám soubor do processed/")
                transcriber.move_processed_file(input_path, settings.processed_folder)
            else:
                transcriber.logger.info("Worker mode: Ponechávám soubor na místě")
            
            sys.exit(0)
            
        except Exception as e:
            transcriber.logger.error(f"Worker mode: Zpracování selhalo: {e}")
            print(f"CHYBA: Zpracovani selhalo: {input_path.name}")
            print(f"Detail: {e}")
            sys.exit(1)
    else:
        # STANDALONE MODE: Zpracování všech čekájících souborů
        transcriber.logger.info("Standalone mode: Zpracovávám všechny čekající soubory")
        stats = await transcriber.process_all_pending()
        
        print(f"\\nStatistiky zpracovani:")
        print(f"Uspesne zpracovano: {stats['processed']}")
        print(f"Chyby: {stats['failed']}")
        print(f"Celkem souboru: {stats['total']}")


if __name__ == "__main__":
    asyncio.run(main())
