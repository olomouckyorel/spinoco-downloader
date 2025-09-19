"""
Main Whisper Transcription Engine

High-quality audio transcription using OpenAI Whisper Large-v3
optimized for Czech technical support calls about heating systems.
"""

import json
import time
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import whisper
import torch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import settings, Settings
from .logger import get_logger, setup_logging, TranscriptionLogger


class WhisperTranscriber:
    """High-quality Whisper transcription engine"""
    
    def __init__(self, custom_settings: Optional[Settings] = None):
        self.settings = custom_settings or settings
        self.settings.ensure_directories()
        
        # Setup logging
        setup_logging(
            level=self.settings.log_level,
            format_type=self.settings.log_format
        )
        
        self.logger = TranscriptionLogger()
        self.model = None
        self.device = None
        
        # Load Whisper model
        self._load_model()
    
    def _load_model(self) -> None:
        """Load Whisper model with optimal configuration"""
        start_time = time.time()
        
        try:
            # Determine device
            self.device = self.settings.get_whisper_device()
            
            self.logger.logger.info(
                f"🧠 Loading Whisper model {self.settings.whisper_model} on {self.device}"
            )
            
            # Load model
            self.model = whisper.load_model(
                self.settings.whisper_model,
                device=self.device
            )
            
            load_time = time.time() - start_time
            self.logger.model_loaded(
                model=self.settings.whisper_model,
                device=self.device,
                load_time=load_time
            )
            
        except Exception as e:
            self.logger.model_load_failed(
                model=self.settings.whisper_model,
                error=str(e)
            )
            raise
    
    def transcribe_audio(self, audio_file: Path) -> Dict[str, Any]:
        """
        Transcribe single audio file with maximum quality
        
        Args:
            audio_file: Path to audio file (.ogg, .wav, .mp3, etc.)
            
        Returns:
            Dictionary containing transcript and metadata
        """
        start_time = time.time()
        
        self.logger.transcription_started(
            filename=audio_file.name,
            model=self.settings.whisper_model,
            device=self.device
        )
        
        try:
            # Get Whisper configuration
            whisper_config = self.settings.get_whisper_config()
            
            # Transcribe with optimized settings
            result = self.model.transcribe(str(audio_file), **whisper_config)
            
            processing_time = time.time() - start_time
            
            # Process results
            transcript_data = self._process_whisper_result(
                result, audio_file, processing_time
            )
            
            self.logger.transcription_completed(
                filename=audio_file.name,
                duration=transcript_data["metadata"]["duration_seconds"],
                word_count=transcript_data["metadata"]["word_count"],
                processing_time=processing_time,
                avg_confidence=transcript_data["quality"]["avg_confidence"]
            )
            
            # Quality check
            if transcript_data["quality"]["avg_confidence"] < 0.7:
                self.logger.quality_warning(
                    filename=audio_file.name,
                    avg_confidence=transcript_data["quality"]["avg_confidence"],
                    threshold=0.7
                )
            
            return transcript_data
            
        except Exception as e:
            self.logger.transcription_failed(
                filename=audio_file.name,
                error=str(e)
            )
            raise
    
    def _process_whisper_result(
        self, 
        result: Dict[str, Any], 
        audio_file: Path, 
        processing_time: float
    ) -> Dict[str, Any]:
        """Process raw Whisper result into structured format"""
        
        # Extract basic info
        full_text = result["text"].strip()
        segments = result.get("segments", [])
        
        # Calculate statistics
        word_count = len(full_text.split())
        total_confidence = 0
        segment_count = len(segments)
        
        processed_segments = []
        
        for segment in segments:
            segment_data = {
                "start": round(segment["start"], 2),
                "end": round(segment["end"], 2),
                "text": segment["text"].strip(),
                "confidence": round(segment.get("avg_logprob", -1), 3),
                "no_speech_prob": round(segment.get("no_speech_prob", 0), 3)
            }
            
            # Add word-level data if available
            if "words" in segment and segment["words"]:
                segment_data["words"] = [
                    {
                        "word": word["word"],
                        "start": round(word["start"], 2),
                        "end": round(word["end"], 2),
                        "probability": round(word.get("probability", 0), 3)
                    }
                    for word in segment["words"]
                ]
            
            processed_segments.append(segment_data)
            total_confidence += segment.get("avg_logprob", -1)
        
        # Calculate average confidence (convert from log prob to 0-1 scale)
        avg_confidence = 0
        if segment_count > 0:
            avg_log_prob = total_confidence / segment_count
            # Convert log probability to confidence (approximate)
            avg_confidence = max(0, min(1, (avg_log_prob + 3) / 3))
        
        return {
            "metadata": {
                "source_file": audio_file.name,
                "source_path": str(audio_file),
                "duration_seconds": round(result.get("duration", 0), 2),
                "language": result.get("language", self.settings.whisper_language),
                "model": self.settings.whisper_model,
                "device": self.device,
                "processing_time_seconds": round(processing_time, 2),
                "transcribed_at": datetime.now().isoformat(),
                "word_count": word_count,
                "settings": {
                    "temperature": self.settings.temperature,
                    "beam_size": self.settings.beam_size,
                    "best_of": self.settings.best_of,
                    "initial_prompt": self.settings.initial_prompt if self.settings.technical_prompt else None
                }
            },
            "transcript": {
                "full_text": full_text,
                "segments": processed_segments
            },
            "quality": {
                "avg_confidence": round(avg_confidence, 3),
                "total_segments": segment_count,
                "low_confidence_segments": sum(1 for s in processed_segments if s["confidence"] < 0.5),
                "no_speech_probability": round(
                    sum(s["no_speech_prob"] for s in processed_segments) / max(1, segment_count), 3
                )
            }
        }
    
    def save_transcript(self, transcript_data: Dict[str, Any]) -> Tuple[Path, Path]:
        """
        Save transcript as text file and metadata as JSON
        
        Args:
            transcript_data: Processed transcript data
            
        Returns:
            Tuple of (text_file_path, metadata_file_path)
        """
        source_file = transcript_data["metadata"]["source_file"]
        base_name = Path(source_file).stem
        
        # Save plain text transcript
        text_file = self.settings.get_output_path() / f"{base_name}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(transcript_data["transcript"]["full_text"])
        
        # Save detailed metadata
        metadata_file = self.settings.get_metadata_path() / f"{base_name}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        
        return text_file, metadata_file
    
    def process_file(self, audio_file: Path) -> Optional[Tuple[Path, Path]]:
        """
        Process single audio file: transcribe and save
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Tuple of output file paths or None if failed
        """
        try:
            # Check if already processed
            base_name = audio_file.stem
            text_file = self.settings.get_output_path() / f"{base_name}.txt"
            
            if text_file.exists() and self.settings.skip_existing:
                self.logger.file_skipped(
                    filename=audio_file.name,
                    reason="already transcribed"
                )
                metadata_file = self.settings.get_metadata_path() / f"{base_name}_metadata.json"
                return text_file, metadata_file
            
            # Transcribe
            transcript_data = self.transcribe_audio(audio_file)
            
            # Save
            output_files = self.save_transcript(transcript_data)
            
            return output_files
            
        except Exception as e:
            self.logger.transcription_failed(
                filename=audio_file.name,
                error=str(e)
            )
            return None
    
    def find_audio_files(self) -> List[Path]:
        """Find all audio files in input directory"""
        input_dir = self.settings.get_input_path()
        
        if not input_dir.exists():
            return []
        
        # Supported audio formats
        audio_extensions = {'.ogg', '.wav', '.mp3', '.m4a', '.flac', '.aac'}
        
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(input_dir.glob(f"*{ext}"))
        
        return sorted(audio_files)
    
    def find_pending_files(self) -> List[Path]:
        """Find audio files that don't have corresponding transcripts"""
        audio_files = self.find_audio_files()
        
        if not audio_files:
            return []
        
        pending = []
        output_dir = self.settings.get_output_path()
        
        for audio_file in audio_files:
            text_file = output_dir / f"{audio_file.stem}.txt"
            if not text_file.exists() or not self.settings.skip_existing:
                pending.append(audio_file)
        
        return pending
    
    def process_batch(self) -> Dict[str, int]:
        """
        Process all pending audio files
        
        Returns:
            Processing statistics
        """
        pending_files = self.find_pending_files()
        
        if not pending_files:
            self.logger.logger.info("✅ No pending files to transcribe")
            return {"processed": 0, "failed": 0, "skipped": 0}
        
        self.logger.batch_started(total_files=len(pending_files))
        
        stats = {"processed": 0, "failed": 0, "skipped": 0}
        start_time = time.time()
        
        for i, audio_file in enumerate(pending_files, 1):
            self.logger.batch_progress(
                current=i,
                total=len(pending_files),
                filename=audio_file.name
            )
            
            result = self.process_file(audio_file)
            
            if result:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
        
        total_time = time.time() - start_time
        
        self.logger.batch_completed(
            processed=stats["processed"],
            failed=stats["failed"],
            skipped=stats["skipped"],
            total_time=total_time
        )
        
        return stats


class FileWatchHandler(FileSystemEventHandler):
    """File system event handler for watch mode"""
    
    def __init__(self, transcriber: WhisperTranscriber):
        self.transcriber = transcriber
        super().__init__()
    
    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if it's an audio file
        if file_path.suffix.lower() in {'.ogg', '.wav', '.mp3', '.m4a', '.flac', '.aac'}:
            self.transcriber.logger.new_file_detected(filename=file_path.name)
            
            # Small delay to ensure file is fully written
            time.sleep(2)
            
            # Process the file
            self.transcriber.process_file(file_path)


def run_watch_mode(transcriber: WhisperTranscriber) -> None:
    """Run transcriber in watch mode"""
    input_dir = transcriber.settings.get_input_path()
    
    transcriber.logger.watch_mode_started(
        directory=str(input_dir),
        interval=transcriber.settings.watch_interval
    )
    
    event_handler = FileWatchHandler(transcriber)
    observer = Observer()
    observer.schedule(event_handler, str(input_dir), recursive=False)
    
    observer.start()
    
    try:
        while True:
            time.sleep(transcriber.settings.watch_interval)
    except KeyboardInterrupt:
        transcriber.logger.logger.info("🛑 Watch mode stopped")
        observer.stop()
    
    observer.join()


def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(
        description="Spinoco Whisper Transcriber - High-quality audio transcription"
    )
    
    parser.add_argument(
        "--file", 
        type=str, 
        help="Transcribe single audio file"
    )
    
    parser.add_argument(
        "--process-all", 
        action="store_true",
        help="Process all pending files in input directory"
    )
    
    parser.add_argument(
        "--watch", 
        action="store_true",
        help="Run in watch mode - continuously monitor input directory"
    )
    
    parser.add_argument(
        "--model", 
        type=str,
        choices=["tiny", "base", "small", "medium", "large", "large-v3"],
        help="Override Whisper model"
    )
    
    parser.add_argument(
        "--device", 
        type=str,
        choices=["auto", "cpu", "cuda"],
        help="Override device selection"
    )
    
    parser.add_argument(
        "--no-skip", 
        action="store_true",
        help="Process all files, including those already transcribed"
    )
    
    args = parser.parse_args()
    
    # Create custom settings if needed
    custom_settings = None
    if any([args.model, args.device, args.no_skip]):
        custom_settings = Settings()
        if args.model:
            custom_settings.whisper_model = args.model
        if args.device:
            custom_settings.whisper_device = args.device
        if args.no_skip:
            custom_settings.skip_existing = False
    
    # Create transcriber
    transcriber = WhisperTranscriber(custom_settings)
    
    try:
        if args.file:
            # Single file processing
            audio_file = Path(args.file)
            if not audio_file.exists():
                print(f"❌ File not found: {audio_file}")
                return 1
            
            result = transcriber.process_file(audio_file)
            if result:
                text_file, metadata_file = result
                print(f"✅ Transcribed: {text_file}")
                print(f"📊 Metadata: {metadata_file}")
                return 0
            else:
                print(f"❌ Failed to transcribe: {audio_file}")
                return 1
        
        elif args.watch:
            # Watch mode
            run_watch_mode(transcriber)
            return 0
        
        elif args.process_all:
            # Batch processing
            stats = transcriber.process_batch()
            print(f"📊 Processing complete:")
            print(f"   ✅ Processed: {stats['processed']}")
            print(f"   ❌ Failed: {stats['failed']}")
            print(f"   ⏭️ Skipped: {stats['skipped']}")
            
            return 0 if stats['failed'] == 0 else 1
        
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())


