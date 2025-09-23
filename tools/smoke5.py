#!/usr/bin/env python3
"""
tools/smoke5.py - One-shot smoke test na 5 nahrávek

Sekvenčně spustí:
1) steps/01_ingest_spinoco/run.py (limit=5, incr)
2) steps/02_transcribe_asr_adapter/run.py (nad výstupem z 01)

Bez Prefectu, bez dalších parametrů. "Spusť a sleduj".
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import time

# Použijeme python z aktuálního venv
REPO = Path(__file__).resolve().parents[1]
PY = sys.executable  # ← tohle je python z aktuálního venv!

INGEST = REPO / "steps" / "ingest_spinoco" / "run.py"
TRANS = REPO / "steps" / "transcribe_asr_adapter" / "run.py"


class Colors:
    """Barevný výstup pro lepší čitelnost."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_colored(message: str, color: str = Colors.WHITE, bold: bool = False):
    """Vytiskne barevnou zprávu."""
    prefix = Colors.BOLD if bold else ""
    print(f"{prefix}{color}{message}{Colors.END}")


def print_header(title: str):
    """Vytiskne hlavičku sekce."""
    print_colored(f"\n{'='*60}", Colors.CYAN, bold=True)
    print_colored(f" {title}", Colors.CYAN, bold=True)
    print_colored(f"{'='*60}", Colors.CYAN, bold=True)


def print_step(step: str, status: str = "RUNNING"):
    """Vytiskne stav kroku."""
    status_color = Colors.YELLOW if status == "RUNNING" else Colors.GREEN if status == "SUCCESS" else Colors.RED
    print_colored(f"\n🔧 {step} [{status}]", status_color, bold=True)


def check_config_exists(config_path: Path) -> bool:
    """Zkontroluje existenci konfiguračního souboru."""
    if not config_path.exists():
        print_colored(f"❌ Chybí konfigurační soubor: {config_path}", Colors.RED, bold=True)
        print_colored(f"   Zkopíruj {config_path.with_suffix('.example.yaml')} a vyplň token", Colors.YELLOW)
        return False
    return True


def run_step(title: str, args: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """
    Spustí krok pipeline a vrátí výsledek.
    
    Args:
        title: Název kroku pro výpis
        args: Argumenty pro python script (bez 'python')
        cwd: Pracovní adresář
        
    Returns:
        CompletedProcess: Výsledek spuštění
    """
    print_step(title, "RUNNING")
    
    # Použijeme python z venv a zdědíme environment
    env = os.environ.copy()  # zdědí VIRTUAL_ENV, PATH, atd.
    cmd = [PY] + [str(a) for a in args]  # ← spouštíme přes venv python
    
    print_colored(f"Příkaz: {' '.join(cmd)}", Colors.BLUE)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            env=env,
            capture_output=True,
            text=True,
            check=False
        )
        
        duration = time.time() - start_time
        
        # Vytiskni výstup
        if result.stdout:
            print_colored("STDOUT:", Colors.GREEN)
            print(result.stdout)
        
        if result.stderr:
            print_colored("STDERR:", Colors.RED)
            print(result.stderr)
        
        # Urči status
        if result.returncode == 0:
            print_step(title, "SUCCESS")
            print_colored(f"✅ Dokončeno za {duration:.1f}s", Colors.GREEN)
        else:
            print_step(title, "FAILED")
            print_colored(f"❌ Selhalo s kódem {result.returncode} za {duration:.1f}s", Colors.RED)
        
        return result
        
    except Exception as e:
        print_step(title, "ERROR")
        print_colored(f"❌ Chyba při spuštění: {e}", Colors.RED)
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def find_latest_run(step_dir: Path) -> Optional[Path]:
    """
    Najde nejnovější run v adresáři kroku.
    
    Args:
        step_dir: Adresář kroku (např. steps/01_ingest_spinoco/output/runs)
        
    Returns:
        Path: Cesta k nejnovějšímu runu nebo None
    """
    runs_dir = step_dir / "output" / "runs"
    
    if not runs_dir.exists():
        return None
    
    # Najdi všechny adresáře s ULID názvy
    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    
    if not run_dirs:
        return None
    
    # Seřaď lexikograficky (ULID se řadí správně podle času)
    latest_run = max(run_dirs, key=lambda x: x.name)
    
    # Ověř že má manifest.json
    manifest_path = latest_run / "manifest.json"
    if not manifest_path.exists():
        return None
    
    return latest_run


def read_metrics(path: Path) -> Dict[str, Any]:
    """
    Načte metriky z JSON souboru.
    
    Args:
        path: Cesta k metrics.json
        
    Returns:
        Dict: Metriky nebo prázdný dict
    """
    if not path.exists():
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print_colored(f"⚠️ Chyba při čtení metrik z {path}: {e}", Colors.YELLOW)
        return {}


def read_manifest(path: Path) -> Dict[str, Any]:
    """
    Načte manifest z JSON souboru.
    
    Args:
        path: Cesta k manifest.json
        
    Returns:
        Dict: Manifest nebo prázdný dict
    """
    if not path.exists():
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print_colored(f"⚠️ Chyba při čtení manifestu z {path}: {e}", Colors.YELLOW)
        return {}


def main():
    """Hlavní funkce smoke testu."""
    parser = argparse.ArgumentParser(description="Smoke test na 5 nahrávek")
    parser.add_argument('--limit', type=int, default=5, help='Počet nahrávek k testování (default: 5)')
    args = parser.parse_args()
    
    print_header("SMOKE TEST - 5 NAHRÁVEK")
    print_colored(f"Limit: {args.limit} nahrávek", Colors.CYAN)
    
    # Zkontroluj konfigurace
    print_header("KONTROLA KONFIGURACÍ")
    
    ingest_config = Path("steps/ingest_spinoco/input/config.yaml")
    transcribe_config = Path("steps/transcribe_asr_adapter/input/config.yaml")
    
    if not check_config_exists(ingest_config):
        return 1
    
    if not check_config_exists(transcribe_config):
        return 1
    
    print_colored("✅ Všechny konfigurace existují", Colors.GREEN)
    
    # Krok 1: Ingest
    print_header("KROK 1: INGEST SPINOCO")
    
    ingest_args = [
        INGEST,
        "--mode", "backfill",
        "--limit", str(args.limit),
        "--max-retry", "2",
        "--config", REPO / "steps/ingest_spinoco/input/config.yaml"
    ]
    
    ingest_result = run_step("INGEST", ingest_args)
    
    if ingest_result.returncode != 0:
        print_colored("❌ Ingest selhal - ukončuji", Colors.RED, bold=True)
        return 1
    
    # Najdi nejnovější ingest run
    print_header("HLEDÁNÍ NEJNOVĚJŠÍHO INGEST RUN")
    
    ingest_run = find_latest_run(Path("steps/ingest_spinoco"))
    
    if not ingest_run:
        print_colored("❌ Nepodařilo se najít nejnovější ingest run", Colors.RED, bold=True)
        return 1
    
    print_colored(f"✅ Nalezen ingest run: {ingest_run.name}", Colors.GREEN)
    
    # Ověř že má audio soubory
    audio_dir = ingest_run / "data" / "audio"
    if not audio_dir.exists():
        print_colored("❌ Ingest run nemá audio adresář", Colors.RED, bold=True)
        return 1
    
    audio_files = list(audio_dir.glob("*.ogg"))
    print_colored(f"✅ Nalezeno {len(audio_files)} audio souborů", Colors.GREEN)
    
    # Krok 2: Transcribe
    print_header("KROK 2: TRANSCRIBE ASR ADAPTER")
    
    transcribe_args = [
        TRANS,
        "--mode", "incr",
        "--input-run", ingest_run.name,
        "--limit", str(args.limit),
        "--max-retry", "2",
        "--config", REPO / "steps/transcribe_asr_adapter/input/config.yaml"
    ]
    
    transcribe_result = run_step("TRANSCRIBE", transcribe_args)
    
    # Najdi nejnovější transcribe run
    print_header("HLEDÁNÍ NEJNOVĚJŠÍHO TRANSCRIBE RUN")
    
    transcribe_run = find_latest_run(Path("steps/transcribe_asr_adapter"))
    
    if not transcribe_run:
        print_colored("❌ Nepodařilo se najít nejnovější transcribe run", Colors.RED, bold=True)
        return 1
    
    print_colored(f"✅ Nalezen transcribe run: {transcribe_run.name}", Colors.GREEN)
    
    # Shrnutí
    print_header("SHRNUTÍ VÝSLEDKŮ")
    
    # Načti manifesty a metriky
    ingest_manifest = read_manifest(ingest_run / "manifest.json")
    ingest_metrics = read_metrics(ingest_run / "metrics.json")
    
    transcribe_manifest = read_manifest(transcribe_run / "manifest.json")
    transcribe_metrics = read_metrics(transcribe_run / "metrics.json")
    
    # Vytiskni cesty
    print_colored("📁 CESTY K SOUBORŮM:", Colors.CYAN, bold=True)
    print_colored(f"  INGEST manifest:   {ingest_run / 'manifest.json'}", Colors.WHITE)
    print_colored(f"  INGEST metrics:    {ingest_run / 'metrics.json'}", Colors.WHITE)
    print_colored(f"  TRANSCRIBE manifest: {transcribe_run / 'manifest.json'}", Colors.WHITE)
    print_colored(f"  TRANSCRIBE metrics:  {transcribe_run / 'metrics.json'}", Colors.WHITE)
    
    # Vytiskni metriky
    print_colored("\n📊 METRIKY:", Colors.CYAN, bold=True)
    
    # Ingest metriky
    ingest_recordings = ingest_metrics.get('recordings_total', 0)
    ingest_downloaded = ingest_metrics.get('downloaded_ok', 0)
    ingest_failed = ingest_metrics.get('failed', 0)
    
    print_colored(f"  INGEST:", Colors.WHITE)
    print_colored(f"    📥 Recordings total: {ingest_recordings}", Colors.WHITE)
    print_colored(f"    ✅ Downloaded OK:     {ingest_downloaded}", Colors.GREEN)
    print_colored(f"    ❌ Failed:            {ingest_failed}", Colors.RED)
    
    # Transcribe metriky
    transcribe_recordings = transcribe_metrics.get('recordings_total', 0)
    transcribe_transcribed = transcribe_metrics.get('transcribed_ok', 0)
    transcribe_failed = transcribe_metrics.get('failed', 0)
    transcribe_calls = transcribe_metrics.get('calls_total', 0)
    
    print_colored(f"  TRANSCRIBE:", Colors.WHITE)
    print_colored(f"    📥 Recordings total: {transcribe_recordings}", Colors.WHITE)
    print_colored(f"    ✅ Transcribed OK:    {transcribe_transcribed}", Colors.GREEN)
    print_colored(f"    ❌ Failed:            {transcribe_failed}", Colors.RED)
    print_colored(f"    📞 Calls total:       {transcribe_calls}", Colors.WHITE)
    
    # Zkontroluj výstupní soubory
    print_colored("\n📄 VÝSTUPNÍ SOUBORY:", Colors.CYAN, bold=True)
    
    transcripts_recordings = transcribe_run / "data" / "transcripts_recordings.jsonl"
    transcripts_calls = transcribe_run / "data" / "transcripts_calls.jsonl"
    
    if transcripts_recordings.exists():
        print_colored(f"  ✅ transcripts_recordings.jsonl: {transcripts_recordings}", Colors.GREEN)
    else:
        print_colored(f"  ❌ transcripts_recordings.jsonl: CHYBÍ", Colors.RED)
    
    if transcripts_calls.exists():
        print_colored(f"  ✅ transcripts_calls.jsonl: {transcripts_calls}", Colors.GREEN)
    else:
        print_colored(f"  ❌ transcripts_calls.jsonl: CHYBÍ", Colors.RED)
    
    # Urči finální status
    print_header("FINÁLNÍ STATUS")
    
    if transcribe_result.returncode == 0:
        print_colored("🎉 SMOKE TEST ÚSPĚŠNÝ!", Colors.GREEN, bold=True)
        print_colored(f"\n💡 Prohlédni si výsledky:", Colors.CYAN)
        print_colored(f"   📖 Otevři: {transcripts_calls}", Colors.YELLOW)
        return 0
    else:
        # Zkontroluj jestli je to partial success
        error_json = transcribe_run / "error.json"
        if error_json.exists():
            print_colored("⚠️ SMOKE TEST ČÁSTEČNĚ ÚSPĚŠNÝ (partial success)", Colors.YELLOW, bold=True)
            print_colored(f"   📖 Otevři: {transcripts_calls}", Colors.YELLOW)
            return 0
        else:
            print_colored("❌ SMOKE TEST SELHAL", Colors.RED, bold=True)
            return 1


if __name__ == "__main__":
    sys.exit(main())
