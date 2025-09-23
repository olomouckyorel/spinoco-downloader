#!/usr/bin/env python3
"""
Rychlý test pro steps/transcribe_asr_adapter.
"""

import sys
import tempfile
import json
from pathlib import Path

# Přidej root do path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Test importů
    from steps.transcribe_asr_adapter.adapter import normalize_recording, normalize_call_level
    print("✅ Adapter import OK")
    
    from steps.transcribe_asr_adapter.run import TranscribeState
    print("✅ TranscribeState import OK")
    
    from common.lib import State, Manifest
    print("✅ Common library import OK")
    
    print("\n🧪 Testování adapter funkcí...")
    
    # Test normalize_recording
    transcript_json = {
        "transcription": {
            "text": "Testovací přepis hovoru o technické podpoře.",
            "language": "cs",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 5.2,
                    "text": " Testovací přepis hovoru"
                }
            ]
        },
        "metadata": {
            "duration": 5.2,
            "whisper_model": "large-v3",
            "device_used": "cpu",
            "beam_size": 5,
            "processed_at": "2024-08-22T05:43:36Z"
        }
    }
    
    normalized = normalize_recording(
        transcript_json, 
        "20240822_054336_71da9579_p01", 
        "20240822_054336_71da9579",
        "audio/20240822_054336_71da9579_p01.ogg"
    )
    
    print(f"✅ normalize_recording: {normalized['recording_id']}")
    print(f"   - ASR model: {normalized['asr']['model']}")
    print(f"   - Segments: {normalized['metrics']['seg_count']}")
    print(f"   - Text length: {len(normalized['text'])}")
    
    # Test normalize_call_level
    call_transcript = normalize_call_level([normalized])
    print(f"✅ normalize_call_level: {call_transcript['call_id']}")
    print(f"   - Recording count: {call_transcript['metrics']['recording_count']}")
    print(f"   - Total segments: {call_transcript['metrics']['total_segments']}")
    
    # Test TranscribeState
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        state = TranscribeState(str(db_path))
        
        # Test upsert
        result = state.upsert_transcript("rec_001", "call_001", "hash123", "text456")
        print(f"✅ TranscribeState upsert: {result}")
        
        # Test mark_ok
        state.mark_ok("rec_001", "2024-08-22T05:43:36Z")
        print("✅ TranscribeState mark_ok")
        
        # Test stats
        stats = state.get_stats()
        print(f"✅ TranscribeState stats: {stats['total_transcripts']} transcripts")
        
        state.close()
    
    print("\n🎉 Všechny testy prošly!")
    
except Exception as e:
    print(f"❌ Test error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
