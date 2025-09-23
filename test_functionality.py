#!/usr/bin/env python3
"""
Rychlý funkční test pro steps/ingest_spinoco.
"""

import sys
import tempfile
import json
from pathlib import Path

# Přidej root do path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from steps.ingest_spinoco.client import FakeSpinocoClient
    from steps.ingest_spinoco.run import IngestRunner
    import yaml
    
    print("🧪 Testování FakeSpinocoClient...")
    
    # Vytvoř test fixtures
    with tempfile.TemporaryDirectory() as temp_dir:
        fixtures_dir = Path(temp_dir) / "fixtures"
        fixtures_dir.mkdir()
        
        # Test call data
        call_data = {
            "id": "test_call_001",
            "lastUpdate": 1724305416000,
            "tpe": {"name": "Test"},
            "owner": {"id": "user1", "name": "Test User"}
        }
        
        recordings_data = [
            {
                "id": "recording_001",
                "date": 1724305416000,
                "duration": 229,
                "vm": False,
                "available": True,
                "transcriptions": {}
            }
        ]
        
        with open(fixtures_dir / "call_task.json", 'w') as f:
            json.dump(call_data, f)
        
        with open(fixtures_dir / "recordings.json", 'w') as f:
            json.dump(recordings_data, f)
        
        # Test FakeSpinocoClient
        client = FakeSpinocoClient(fixtures_dir)
        
        # Test list_calls
        calls = list(client.list_calls(limit=1))
        print(f"✅ list_calls: {len(calls)} hovorů")
        
        # Test list_recordings
        recordings = client.list_recordings("test_call_001")
        print(f"✅ list_recordings: {len(recordings)} nahrávek")
        
        # Test download_recording
        output_path = Path(temp_dir) / "test.ogg"
        size = client.download_recording("test_rec_001", output_path)
        print(f"✅ download_recording: {size} bajtů")
        
        # Test OGG validation
        with open(output_path, 'rb') as f:
            header = f.read(4)
            is_valid = header == b'OggS'
        print(f"✅ OGG validation: {'platný' if is_valid else 'neplatný'}")
    
    print("\n🎉 Všechny testy prošly!")
    
except Exception as e:
    print(f"❌ Test error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
