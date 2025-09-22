#!/usr/bin/env python3
"""
Test Whisper Transcriber - bez složitých importů
"""

import json
import whisper
import torch
from pathlib import Path
from datetime import datetime


def simple_transcribe():
    """Jednoduchý test Whisper transcriberu"""
    
    print("🎙️ Test Whisper Large-v3 Transcriber")
    print("=" * 50)
    
    # Najdeme audio soubory
    input_folder = Path("../data/01_recordings")
    output_folder = Path("./data/transcriptions")
    output_folder.mkdir(parents=True, exist_ok=True)
    
    audio_files = list(input_folder.glob("*.ogg"))
    
    if not audio_files:
        print("❌ Žádné .ogg soubory nenalezeny v:", input_folder)
        return
        
    print(f"📁 Nalezeno {len(audio_files)} audio souborů")
    
    # Načteme Whisper model
    print("🔄 Načítám Whisper Large-v3 model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️ Používám device: {device}")
    
    model = whisper.load_model("large-v3", device=device)
    print("✅ Model načten!")
    
    # Zpracujeme první soubor jako test
    test_file = audio_files[0]
    print(f"\\n🎵 Zpracovávám testovací soubor: {test_file.name}")
    
    # Whisper transcription
    result = model.transcribe(
        str(test_file),
        language="czech",
        temperature=0.0,
        best_of=5,
        beam_size=5,
        condition_on_previous_text=True,
        verbose=True
    )
    
    # Výsledek
    print(f"\\n📝 PŘEPIS:")
    print(f"Text: {result['text']}")
    print(f"Jazyk: {result['language']}")
    print(f"Segmentů: {len(result['segments'])}")
    
    # Uložíme výsledek
    output_file = output_folder / f"{test_file.stem}_transcription.json"
    
    transcription_result = {
        "transcription": {
            "text": result["text"].strip(),
            "language": result["language"],
            "segments": result["segments"]
        },
        "metadata": {
            "original_filename": test_file.name,
            "transcribed_at": datetime.now().isoformat(),
            "whisper_model": "large-v3",
            "audio_file_size": test_file.stat().st_size,
            "device_used": device
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transcription_result, f, ensure_ascii=False, indent=2)
    
    print(f"\\n💾 Výsledek uložen: {output_file}")
    print("\\n🎉 Test dokončen úspěšně!")


if __name__ == "__main__":
    simple_transcribe()