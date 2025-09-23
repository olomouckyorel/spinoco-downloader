#!/usr/bin/env python3
"""
Rychlý test pro steps/anonymize.
"""

import sys
import tempfile
import json
from pathlib import Path

# Přidej root do path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Test importů
    from steps.anonymize.anonymizer import PIIAnonymizer, redact_recording, redact_call
    print("✅ Anonymizer import OK")
    
    from steps.anonymize.run import AnonymizeRunner
    print("✅ AnonymizeRunner import OK")
    
    from common.lib import Manifest
    print("✅ Common library import OK")
    
    print("\n🧪 Testování anonymizer funkcí...")
    
    # Test PIIAnonymizer
    config = {
        'tags_prefix': '@',
        'redact_phone': True,
        'redact_email': True,
        'redact_iban': True
    }
    
    anonymizer = PIIAnonymizer(config)
    
    # Test redigování textu
    text = "Zavolejte na +420 123 456 789 nebo napište na info@firma.cz. IBAN je CZ65 0800 0000 1920 0014 5399"
    context = {}
    
    redacted, counts = anonymizer.redact_text(text, context)
    
    print(f"✅ redact_text: {redacted}")
    print(f"   - Counts: {counts}")
    print(f"   - Context: {context}")
    
    # Test vault map
    vault_map = anonymizer.create_vault_map(context)
    print(f"✅ create_vault_map: {len(vault_map)} entries")
    
    # Test redact_recording
    recording = {
        'call_id': '20240822_054336_71da9579',
        'recording_id': '20240822_054336_71da9579_p01',
        'text': 'Zavolejte na +420 123 456 789',
        'segments': [
            {
                'start': 0.0,
                'end': 5.0,
                'text': 'Zavolejte na +420 123 456 789'
            }
        ]
    }
    
    redacted_recording = redact_recording(recording, config, {})
    print(f"✅ redact_recording: {redacted_recording['recording_id']}")
    print(f"   - PII stats: {redacted_recording['pii_stats']}")
    print(f"   - Redacted text: {redacted_recording['text']}")
    
    # Test redact_call
    call = {
        'call_id': '20240822_054336_71da9579',
        'text': 'Zavolejte na +420 123 456 789 nebo napište na info@firma.cz',
        'segments': [
            {
                'start': 0.0,
                'end': 5.0,
                'text': 'Zavolejte na +420 123 456 789',
                'recording_id': '20240822_054336_71da9579_p01'
            }
        ]
    }
    
    redacted_call, vault_map = redact_call(call, config)
    print(f"✅ redact_call: {redacted_call['call_id']}")
    print(f"   - PII stats: {redacted_call['pii_stats']}")
    print(f"   - Vault map: {len(vault_map)} entries")
    
    print("\n🎉 Všechny testy prošly!")
    
except Exception as e:
    print(f"❌ Test error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
