#!/usr/bin/env python3
"""
Rychlý test pro steps/01_ingest_spinoco.
"""

import sys
from pathlib import Path

# Přidej root do path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Test importů
    from steps.ingest_spinoco.client import FakeSpinocoClient
    print("✅ FakeSpinocoClient import OK")
    
    from steps.ingest_spinoco.run import IngestRunner
    print("✅ IngestRunner import OK")
    
    from common.lib import State, Manifest
    print("✅ Common library import OK")
    
    print("\n🎉 Všechny importy fungují!")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
