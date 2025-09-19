"""
Whisper Transcription Module

Converts .ogg audio files to .txt transcripts using OpenAI Whisper Large-v3
for maximum quality transcription of technical support calls.

Input:  data/01_recordings/*.ogg
Output: data/02_transcripts/*.txt
"""

import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import whisper
import torch
from datetime import datetime

from ..logger import get_logger
from ..config import Settings


class TranscriberModule:
    """High-quality audio transcription using Whisper Large-v3"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.logger = get_logger(__name__)
        
        # Directories
        self.input_dir = Path("data/01_recordings")
        self.output_dir = Path("data/02_transcripts")
        self.metadata_dir = Path("data/metadata/transcripts")
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Whisper model
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model with optimal settings for quality"""
        try:
            # Use GPU if available (your Radeon 890M)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.logger.info(f"🎤 Loading Whisper Large-v3 model on {device}")
            
            # Large-v3 for maximum quality
            self.model = whisper.load_model(
                "large-v3",
                device=device,
                download_root=None  # Default cache location
            )
            
            self.logger.info("✅ Whisper model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load Whisper model: {e}")
            raise
    
    def transcribe_file(self, audio_file: Path) -> Dict[str, Any]:
        """
        Transcribe single audio file with maximum quality settings
        
        Args:
            audio_file: Path to .ogg audio file
            
        Returns:
            Dict with transcript and metadata
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"🎤 Transcribing {audio_file.name}")
            
            # Whisper transcription with quality-optimized settings
            result = self.model.transcribe(
                str(audio_file),
                language="cs",              # Czech language
                task="transcribe",          # Not translate
                temperature=0.0,            # Deterministic results
                beam_size=5,               # Quality vs speed (max=5)
                best_of=5,                 # Try 5 different decodings
                patience=1.0,              # Beam search patience
                word_timestamps=True,      # Word-level timestamps
                prepend_punctuations="\"'"¿([{-",
                append_punctuations="\"'.。,，!！?？:：")]}、",
                initial_prompt="Toto je nahrávka technické podpory pro kotle a topení. Obsahuje technické termíny, kódy chyb a návody na opravu."
            )
            
            processing_time = time.time() - start_time
            
            # Extract transcript data
            transcript_data = {
                "metadata": {
                    "source_file": audio_file.name,
                    "duration_seconds": result.get("duration", 0),
                    "language": result.get("language", "cs"),
                    "model": "whisper-large-v3",
                    "processing_time_seconds": round(processing_time, 2),
                    "transcribed_at": datetime.now().isoformat(),
                    "word_count": len(result["text"].split()),
                },
                "transcript": {
                    "full_text": result["text"].strip(),
                    "segments": []
                },
                "quality": {
                    "avg_logprob": 0,  # Will calculate from segments
                    "no_speech_prob": 0,
                    "total_segments": len(result.get("segments", []))
                }
            }
            
            # Process segments for detailed data
            total_logprob = 0
            for segment in result.get("segments", []):
                segment_data = {
                    "start": round(segment["start"], 2),
                    "end": round(segment["end"], 2), 
                    "text": segment["text"].strip(),
                    "avg_logprob": round(segment.get("avg_logprob", 0), 3),
                    "no_speech_prob": round(segment.get("no_speech_prob", 0), 3)
                }
                
                # Add word-level timestamps if available
                if "words" in segment:
                    segment_data["words"] = [
                        {
                            "word": word["word"],
                            "start": round(word["start"], 2),
                            "end": round(word["end"], 2),
                            "probability": round(word.get("probability", 0), 3)
                        }
                        for word in segment["words"]
                    ]
                
                transcript_data["transcript"]["segments"].append(segment_data)
                total_logprob += segment.get("avg_logprob", 0)
            
            # Calculate quality metrics
            if transcript_data["quality"]["total_segments"] > 0:
                transcript_data["quality"]["avg_logprob"] = round(
                    total_logprob / transcript_data["quality"]["total_segments"], 3
                )
            
            self.logger.info(
                f"✅ Transcription completed",
                file=audio_file.name,
                duration=f"{processing_time:.1f}s",
                words=transcript_data["metadata"]["word_count"],
                segments=transcript_data["quality"]["total_segments"]
            )
            
            return transcript_data
            
        except Exception as e:
            self.logger.error(f"❌ Transcription failed for {audio_file.name}: {e}")
            raise
    
    def save_transcript(self, transcript_data: Dict[str, Any], output_file: Path) -> None:
        """Save transcript as plain text file"""
        try:
            # Save plain text transcript
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcript_data["transcript"]["full_text"])
            
            # Save detailed metadata as JSON
            metadata_file = self.metadata_dir / f"{output_file.stem}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"💾 Saved transcript: {output_file.name}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save transcript: {e}")
            raise
    
    def process_file(self, audio_file: Path) -> Optional[Path]:
        """
        Process single audio file: transcribe and save
        
        Args:
            audio_file: Path to .ogg file
            
        Returns:
            Path to output .txt file or None if failed
        """
        try:
            # Generate output filename (same stem, .txt extension)
            output_file = self.output_dir / f"{audio_file.stem}.txt"
            
            # Skip if already processed
            if output_file.exists():
                self.logger.info(f"⏭️ Skipping {audio_file.name} - already transcribed")
                return output_file
            
            # Transcribe
            transcript_data = self.transcribe_file(audio_file)
            
            # Save
            self.save_transcript(transcript_data, output_file)
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"❌ Failed to process {audio_file.name}: {e}")
            return None
    
    def find_pending_files(self) -> List[Path]:
        """Find all .ogg files that don't have corresponding .txt files"""
        if not self.input_dir.exists():
            self.logger.warning(f"Input directory {self.input_dir} does not exist")
            return []
        
        ogg_files = list(self.input_dir.glob("*.ogg"))
        pending = []
        
        for ogg_file in ogg_files:
            txt_file = self.output_dir / f"{ogg_file.stem}.txt"
            if not txt_file.exists():
                pending.append(ogg_file)
        
        return pending
    
    def process_all_pending(self) -> Dict[str, int]:
        """
        Process all pending .ogg files
        
        Returns:
            Statistics dictionary
        """
        pending_files = self.find_pending_files()
        
        if not pending_files:
            self.logger.info("✅ No pending files to transcribe")
            return {"processed": 0, "failed": 0, "skipped": 0}
        
        self.logger.info(f"🎤 Found {len(pending_files)} files to transcribe")
        
        stats = {"processed": 0, "failed": 0, "skipped": 0}
        start_time = time.time()
        
        for i, audio_file in enumerate(pending_files, 1):
            self.logger.info(f"📊 Processing {i}/{len(pending_files)}: {audio_file.name}")
            
            result = self.process_file(audio_file)
            
            if result:
                stats["processed"] += 1
            else:
                stats["failed"] += 1
        
        total_time = time.time() - start_time
        
        self.logger.info(
            f"🎉 Transcription batch completed",
            processed=stats["processed"],
            failed=stats["failed"],
            total_time=f"{total_time:.1f}s"
        )
        
        return stats


def main():
    """Standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Transcribe audio files using Whisper")
    parser.add_argument("--file", type=str, help="Transcribe single file")
    parser.add_argument("--process-all", action="store_true", help="Process all pending files")
    
    args = parser.parse_args()
    
    transcriber = TranscriberModule()
    
    if args.file:
        # Single file
        audio_file = Path(args.file)
        if not audio_file.exists():
            print(f"❌ File not found: {audio_file}")
            return
        
        result = transcriber.process_file(audio_file)
        if result:
            print(f"✅ Transcribed: {result}")
        else:
            print(f"❌ Failed to transcribe: {audio_file}")
    
    elif args.process_all:
        # All pending files
        stats = transcriber.process_all_pending()
        print(f"📊 Results: {stats}")
    
    else:
        print("Use --file <path> or --process-all")


if __name__ == "__main__":
    main()


