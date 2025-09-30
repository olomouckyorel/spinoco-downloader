#!/usr/bin/env python3
"""
Spinoco Whisper Transcriber - Main Entry Point
Vysoká kvalita přepisu pomocí OpenAI Whisper Large-v3
"""

import asyncio
import sys
from pathlib import Path

# Přidání src do path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.transcriber import main

if __name__ == "__main__":
    print("Spinoco Whisper Transcriber")
    print("=" * 50)
    print("Vysoka kvalita prepisu pomoci Whisper Large-v3")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\nZpracovani preruseno uzivatelem")
    except Exception as e:
        print(f"\\nCHYBA: Kriticka chyba: {e}")
        sys.exit(1)
