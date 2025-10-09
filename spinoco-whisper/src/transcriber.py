"""
Spinoco Whisper Transcriber
High-quality speech-to-text transcription using OpenAI Whisper Large-v3
"""
import json
import asyncio
import whisper
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import shutil

from .config import settings
from .logger import logger

try:
    import librosa
except ImportError:
    librosa = None

import subprocess
import tempfile


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
    
    def _preprocess_audio_ffmpeg(self, audio_path: Path) -> str:
        """
        FFmpeg preprocessing: OGG/Opus -> 16kHz mono WAV
        Řeší problém s Whisper přeskočením řeči u 8kHz telefonních nahrávek
        """
        tmpdir = Path(tempfile.mkdtemp(prefix="whisper_preproc_"))
        wav_path = tmpdir / "preprocessed.wav"
        
        # FFmpeg: dekódování + resampling + mono konverze + RESET časových značek
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-map", "0:a:0",  # vezmi první audio stream
            "-ac", "1",        # Mono (1 kanál)
            "-ar", "16000",    # 16kHz sampling
            "-c:a", "pcm_s16le", # PCM 16-bit little endian
            "-avoid_negative_ts", "make_zero",  # resetuj PTS na 0
            "-fflags", "+genpts",  # vygeneruj perfektní časové značky
            str(wav_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logger.info(f"Audio preprocessed: {audio_path.name} -> {wav_path.name}")
            return str(wav_path)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg preprocessing failed: {e}")
            raise
        
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
                
    def _load_audio_for_diarization(self, audio_path: Path):
        """
        Načte audio soubor pro diarization (stereo).
        
        Returns:
            Tuple (left_channel, right_channel, sample_rate) nebo None
        """
        if librosa is None:
            return None
        
        try:
            # Načti audio jako stereo
            audio, sr = librosa.load(str(audio_path), sr=None, mono=False)
            
            # Pokud je mono, nemůžeme detekovat
            if audio.ndim == 1:
                self.logger.warning("Audio je MONO, stereo diarization není možná")
                return None
            
            left = audio[0]
            right = audio[1]
            
            return (left, right, sr)
            
        except Exception as e:
            self.logger.warning(f"Chyba při načítání audio pro diarization: {e}")
            return None
    
    def _detect_speaker_from_stereo(self, audio_data, segment_start: float, segment_end: float) -> str:
        """
        Detekuje mluvčího na základě stereo balance (LEFT vs RIGHT kanál).
        
        Args:
            audio_data: Tuple (left, right, sr) z _load_audio_for_diarization
            segment_start: Začátek segmentu v sekundách
            segment_end: Konec segmentu v sekundách
            
        Returns:
            "customer" nebo "technician"
        """
        if audio_data is None:
            return "unknown"
        
        try:
            left, right, sr = audio_data
            
            # Extrahuj segment
            start_sample = int(segment_start * sr)
            end_sample = int(segment_end * sr)
            
            left_segment = left[start_sample:end_sample]
            right_segment = right[start_sample:end_sample]
            
            # Spočti RMS energy
            left_energy = np.sqrt(np.mean(left_segment**2))
            right_energy = np.sqrt(np.mean(right_segment**2))
            
            # Threshold: LEFT musí být 1.5x silnější než RIGHT (nebo naopak)
            threshold = 1.5
            
            if left_energy > right_energy * threshold:
                return "customer"  # LEFT = zákazník
            elif right_energy > left_energy * threshold:
                return "technician"  # RIGHT = technik
            else:
                # Překryv nebo nejasné - použij dominantní kanál
                return "customer" if left_energy > right_energy else "technician"
                
        except Exception as e:
            self.logger.warning(f"Chyba při detekci mluvčího: {e}")
            return "unknown"
    
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
    
    # ========== DUAL-CHANNEL + VAD TRANSCRIPTION ==========
    
    def _split_stereo_to_mono(self, input_ogg: Path) -> tuple[str, str]:
        """
        Rozdělí stereo OGG na 2 mono WAV soubory pomocí FFmpeg pan filtru.
        
        Returns:
            (left_wav_path, right_wav_path)
        """
        tmpdir = Path(tempfile.mkdtemp(prefix="dual_channel_vad_"))
        left_wav = tmpdir / "left.wav"
        right_wav = tmpdir / "right.wav"
        
        # LEFT kanál (FL = Front Left)
        cmd_left = [
            "ffmpeg", "-y", "-i", str(input_ogg),
            "-af", "pan=mono|c0=FL",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(left_wav)
        ]
        
        # RIGHT kanál (FR = Front Right)
        cmd_right = [
            "ffmpeg", "-y", "-i", str(input_ogg),
            "-af", "pan=mono|c0=FR",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(right_wav)
        ]
        
        self.logger.info("Rozdeluji stereo na 2 mono WAV (pan filter FL/FR)...")
        
        subprocess.run(cmd_left, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(cmd_right, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        self.logger.info(f"  LEFT:  {left_wav}")
        self.logger.info(f"  RIGHT: {right_wav}")
        
        return str(left_wav), str(right_wav)
    
    def _get_speech_timestamps_silero(self, wav_path: str) -> List[Dict[str, float]]:
        """
        Použije Silero VAD k detekci speech segments.
        
        Returns:
            List of {"start": float, "end": float} in seconds
        """
        self.logger.info("  Detekuji speech segments (Silero VAD)...")
        
        # Načti Silero VAD model (automaticky stahuje při prvním použití)
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True  # Důvěřujeme Silero VAD
        )
        
        (get_speech_timestamps, _, read_audio, *_) = utils
        
        # Načti audio (Silero očekává 16kHz mono)
        wav = read_audio(wav_path, sampling_rate=16000)
        
        # Detekce speech timestamps
        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=16000,
            threshold=0.5,          # Pravděpodobnost řeči (0.5 = balanced)
            min_speech_duration_ms=250,   # Min délka řeči (250ms)
            min_silence_duration_ms=500,  # Min délka ticha mezi segmenty (500ms)
            window_size_samples=1536,     # 96ms @ 16kHz
            speech_pad_ms=30              # Padding kolem řeči (30ms)
        )
        
        # Převod na sekundy
        segments = []
        for ts in speech_timestamps:
            segments.append({
                "start": ts['start'] / 16000.0,  # samples -> seconds
                "end": ts['end'] / 16000.0
            })
        
        total_speech = sum(s['end'] - s['start'] for s in segments)
        self.logger.info(f"    -> {len(segments)} speech segments, celkem {total_speech:.1f}s")
        
        return segments
    
    def _extract_audio_segment(self, wav_path: str, start: float, end: float, output_path: str):
        """
        Extrahuje audio segment z WAV souboru pomocí FFmpeg.
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-ss", str(start),
            "-to", str(end),
            "-c:a", "pcm_s16le",
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def _transcribe_channel_with_vad(
        self,
        wav_path: str, 
        speaker_label: str,
        tmpdir: Path
    ) -> List[Dict[str, Any]]:
        """
        Přepíše jeden mono kanál Whisperem s VAD preprocessing.
        
        1. Detekuje speech segments pomocí Silero VAD
        2. Extrahuje jen speech segments
        3. Přepisuje každý segment samostatně
        4. Mapuje zpět na původní čas
        """
        self.logger.info(f"Prepisuji {speaker_label} (s VAD preprocessing)...")
        
        # 1. Detekce speech segments
        speech_segments = self._get_speech_timestamps_silero(wav_path)
        
        if not speech_segments:
            self.logger.warning(f"  POZOR: Zadne speech segments detekovany v {speaker_label}!")
            return []
        
        # 2. Přepis každého speech segmentu
        all_segments = []
        segment_dir = tmpdir / f"{speaker_label}_segments"
        segment_dir.mkdir(exist_ok=True)
        
        for i, speech in enumerate(speech_segments):
            # Extrahuj audio segment
            segment_path = segment_dir / f"seg_{i:03d}.wav"
            self._extract_audio_segment(wav_path, speech['start'], speech['end'], str(segment_path))
            
            # Whisper přepis (jen pro tento krátký segment)
            result = self.model.transcribe(
                str(segment_path),
                fp16=False,
                condition_on_previous_text=False,  # Každý segment nezávisle
                temperature=0.0,
                no_speech_threshold=0.6,  # Vyšší (již máme VAD)
                logprob_threshold=-0.5,   # Vyšší důvěra
                compression_ratio_threshold=2.4
            )
            
            # Přidej přeložené segmenty s časovým offsetem
            for seg in result["segments"]:
                all_segments.append({
                    "start": speech['start'] + seg['start'],  # Mapuj zpět na original
                    "end": speech['start'] + seg['end'],
                    "text": seg['text'],
                    "speaker": speaker_label
                })
        
        self.logger.info(f"  {speaker_label}: {len(all_segments)} segmentu z {len(speech_segments)} speech bloku")
        return all_segments
    
    def transcribe_file_dual_channel_vad(self, audio_path: Path) -> Dict[str, Any]:
        """
        Dual-channel transcription s Silero VAD preprocessing.
        
        Tento přístup rozdělí stereo nahrávku na 2 mono kanály (LEFT = customer, RIGHT = technician),
        použije Silero VAD k detekci speech segments, a přepíše každý kanál samostatně.
        Výsledek eliminuje hallucinations a správně rozpoznává mluvčí.
        
        Returns:
            Dict s výsledky přepisu (stejný formát jako transcribe_file)
        """
        self._load_model()
        
        self.logger.info(f"Zacinam DUAL-CHANNEL + VAD prepis souboru: {audio_path.name}")
        
        try:
            # Progress info
            audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"Audio: {audio_size_mb:.1f} MB, model: {settings.whisper_model}, device: {self.device}")
            
            # 1. Rozdělení na 2 mono kanály
            self.logger.info("Rozdeluji stereo na LEFT (customer) + RIGHT (technician)...")
            left_wav, right_wav = self._split_stereo_to_mono(audio_path)
            tmpdir = Path(left_wav).parent
            
            # 2. Přepis LEFT kanál (zákazník) s VAD
            left_segments = self._transcribe_channel_with_vad(left_wav, "customer", tmpdir)
            
            # 3. Přepis RIGHT kanál (technik) s VAD
            right_segments = self._transcribe_channel_with_vad(right_wav, "technician", tmpdir)
            
            # 4. Sloučení segmentů podle času
            self.logger.info("Slucuji segmenty podle casu...")
            all_segments = left_segments + right_segments
            all_segments.sort(key=lambda x: x["start"])
            
            self.logger.info(f"  Celkem: {len(all_segments)} segmentu (customer: {len(left_segments)}, technician: {len(right_segments)})")
            
            # 5. Sestavení kompletního textu
            full_text = " ".join(seg["text"].strip() for seg in all_segments)
            
            # 6. Cleanup temporary files
            try:
                import shutil
                shutil.rmtree(tmpdir)
                self.logger.info("Temporary soubory vycisteny")
            except Exception as e:
                self.logger.warning(f"Nepodarilo se vycistit temporary soubory: {e}")
            
            # 7. Extrakce metadat z názvu souboru
            file_metadata = self._extract_metadata_from_filename(audio_path.name)
            
            # 8. Sestavení výsledku (stejný formát jako transcribe_file)
            transcription_result = {
                "transcription": {
                    "text": full_text,
                    "language": "cs",  # Předpokládáme češtinu
                    "segments": all_segments
                },
                "metadata": {
                    **file_metadata,
                    "transcribed_at": datetime.now().isoformat(),
                    "whisper_model": settings.whisper_model,
                    "audio_file_size": audio_path.stat().st_size,
                    "audio_file_path": str(audio_path),
                    "transcription_method": "dual-channel-vad"
                },
                "processing_info": {
                    "device_used": self.device,
                    "method": "dual-channel + silero-vad",
                    "left_channel_segments": len(left_segments),
                    "right_channel_segments": len(right_segments)
                }
            }
            
            self.logger.info(
                f"Dual-channel + VAD prepis dokoncen: {audio_path.name}",
                text_length=len(full_text),
                segments_count=len(all_segments)
            )
            
            return transcription_result
            
        except Exception as e:
            self.logger.error(f"Chyba pri dual-channel + VAD prepisu {audio_path.name}: {e}")
            raise
    
    # ========== ORIGINAL TRANSCRIPTION METHOD ==========
    
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
            
            # FFmpeg preprocessing pro lepší výsledky (řeší přeskočení řeči)
            self.logger.info("🔧 Preprocessing audio přes FFmpeg...")
            preprocessed_path = self._preprocess_audio_ffmpeg(audio_path)
            
            # Whisper transcription s minimalistickými parametry (jako v asr_fix)
            self.logger.info("⏳ Transkripce běží... (může trvat několik minut)")
            result = self.model.transcribe(
                preprocessed_path,
                # Minimalistické parametry - přesně jako v asr_fix/transcribe_fixed.py
                fp16=False,
                condition_on_previous_text=True,
                temperature=0.0,
                no_speech_threshold=0.0,
                logprob_threshold=-1.0,
                compression_ratio_threshold=2.4
            )
            
            # Cleanup preprocessed souboru
            try:
                Path(preprocessed_path).unlink()
                Path(preprocessed_path).parent.rmdir()
                self.logger.info("Preprocessed soubor vyčištěn")
            except Exception as e:
                self.logger.warning(f"Nepodařilo se vyčistit preprocessed soubor: {e}")
            
            # Detekce mluvčích pro každý segment (stereo-based diarization)
            self.logger.info("Detekuji mluvci na zaklade stereo kanalu...")
            audio_data = self._load_audio_for_diarization(audio_path)
            
            segments_with_speakers = []
            for segment in result["segments"]:
                speaker = self._detect_speaker_from_stereo(
                    audio_data,  # Předáme už načtené audio
                    segment["start"], 
                    segment["end"]
                )
                segment_with_speaker = {**segment, "speaker": speaker}
                segments_with_speakers.append(segment_with_speaker)
            
            # Extrakce metadat z názvu souboru
            file_metadata = self._extract_metadata_from_filename(audio_path.name)
            
            # Sestavení výsledku
            transcription_result = {
                "transcription": {
                    "text": result["text"].strip(),
                    "language": result["language"],
                    "segments": segments_with_speakers  # Segmenty s informací o mluvčím
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
    parser.add_argument('--use-dual-channel-vad', action='store_true',
                       help='Použít dual-channel + Silero VAD přepis (lepší diarization, eliminuje hallucinations)')
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
            # Zpracuj jeden soubor - volba mezi original/dual-channel metodou
            transcriber.logger.info(f"Worker mode: Zpracovávám {input_path.name}")
            
            if args.use_dual_channel_vad:
                transcriber.logger.info("Použití DUAL-CHANNEL + VAD metody")
                result = transcriber.transcribe_file_dual_channel_vad(input_path)
            else:
                transcriber.logger.info("Použití ORIGINAL metody")
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
