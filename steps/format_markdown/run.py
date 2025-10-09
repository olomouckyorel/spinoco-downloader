#!/usr/bin/env python3
"""
steps/04_format_markdown - Převod anonymizovaných transkriptů do čitelného Markdown formátu.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
import yaml

# Import common library
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common.lib import new_run_id, Manifest, create_manifest

from formatter import format_call_to_markdown, format_recording_to_markdown, save_markdown


def now_utc_iso() -> str:
    """Vrátí aktuální UTC čas ve formátu ISO."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


class FormatRunner:
    """Hlavní runner pro formátování do Markdown."""
    
    def __init__(self, config_path: Path, step_run_id: str, flow_run_id: str = None):
        self.config_path = config_path
        self.step_run_id = step_run_id
        self.flow_run_id = flow_run_id
        
        # Načti konfiguraci
        self.config = self._load_config()
        
        # Nastav cesty
        self.step_dir = Path(__file__).parent
        self.output_dir = self.step_dir / "output" / "runs" / step_run_id
        self.data_dir = self.output_dir / "data"
        self.markdown_dir = self.data_dir / "markdown"
        
        # Vytvoř adresáře
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializuj manifest
        self.manifest = self._create_manifest()
    
    def _load_config(self) -> Dict[str, Any]:
        """Načte konfiguraci ze YAML souboru."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _create_manifest(self) -> Manifest:
        """Vytvoří manifest pro tento běh."""
        return create_manifest(
            schema="bh.v1.transcripts_markdown",
            schema_version="1.0.0",
            step_id="04_format_markdown",
            run_mode=self.config.get('run_mode', 'incr'),
            flow_run_id=self.flow_run_id
        )
    
    def load_input_manifest(self, input_run_id: str) -> Dict[str, Any]:
        """Načte manifest z předchozího kroku."""
        input_run_root = Path(self.config['io']['input_run_root'])
        input_manifest_path = input_run_root / input_run_id / "manifest.json"
        
        if not input_manifest_path.exists():
            raise ValueError(f"Input manifest neexistuje: {input_manifest_path}")
        
        with open(input_manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_calls(self, input_run_id: str) -> List[Dict[str, Any]]:
        """Načte call-level transkripty."""
        input_run_root = Path(self.config['io']['input_run_root'])
        calls_path = input_run_root / input_run_id / "data" / self.config['input']['calls_file']
        
        if not calls_path.exists():
            raise ValueError(f"Calls file neexistuje: {calls_path}")
        
        calls = []
        with open(calls_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    calls.append(json.loads(line))
        
        return calls
    
    def format_calls_to_markdown(self, calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Převede calls do Markdown souborů."""
        results = {
            'successful': [],
            'failed': []
        }
        
        for call in calls:
            call_id = call.get('call_id', 'unknown')
            
            try:
                # Formátuj do Markdown
                markdown = format_call_to_markdown(
                    call, 
                    include_metadata=self.config['format'].get('include_metadata', True)
                )
                
                # Ulož
                output_file = self.markdown_dir / f"{call_id}.md"
                save_markdown(markdown, output_file)
                
                results['successful'].append({
                    'call_id': call_id,
                    'output_file': str(output_file.relative_to(self.output_dir))
                })
                
            except Exception as e:
                results['failed'].append({
                    'call_id': call_id,
                    'error': str(e)
                })
        
        return results
    
    def write_metrics(self, results: Dict[str, Any], runtime_s: float) -> Dict[str, Any]:
        """Zapíše metriky."""
        metrics = {
            "calls_total": len(results['successful']) + len(results['failed']),
            "formatted_ok": len(results['successful']),
            "failed": len(results['failed']),
            "runtime_s": runtime_s,
            "throughput_calls_per_min": len(results['successful']) / (runtime_s / 60) if runtime_s > 0 else 0
        }
        
        metrics_path = self.output_dir / "metrics.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        return metrics
    
    def finalize_manifest(self, results: Dict[str, Any], metrics: Dict[str, Any]):
        """Finalizuje manifest."""
        # Přidej input refs
        for result in results['successful']:
            self.manifest.add_input_ref("call_id", result['call_id'])
        
        # Nastav outputs
        self.manifest.set_outputs(
            primary="markdown/"
        )
        
        # Nastav counts
        self.manifest.set_counts(
            calls=metrics['calls_total'],
            formatted=metrics['formatted_ok'],
            failed=metrics['failed']
        )
        
        # Nastav metriky
        self.manifest.merge_metrics(
            throughput_calls_per_min=metrics['throughput_calls_per_min']
        )
        
        # Přidej chyby pokud jsou
        for failed in results['failed']:
            self.manifest.add_error(
                unit_id=failed['call_id'],
                error_key=failed['error'],
                message=f"Formatting failed: {failed['error']}"
            )
        
        # Finalizuj
        if results['failed']:
            self.manifest.finalize_error(partial=True)
            
            # Zapiš error.json
            error_data = {
                "failed_ids": [f['call_id'] for f in results['failed']],
                "reason": "Some calls failed to format"
            }
            error_path = self.output_dir / "error.json"
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
        else:
            self.manifest.finalize_success()
            
            # Zapiš success.ok
            success_path = self.output_dir / "success.ok"
            success_path.touch()
        
        # Validuj a zapiš manifest
        self.manifest.validate()
        self.manifest.write(self.output_dir / "manifest.json")
    
    def run(self, args: argparse.Namespace) -> int:
        """Hlavní běh formátování."""
        start_time = time.time()
        
        try:
            # 1. Načti input manifest
            input_manifest = self.load_input_manifest(args.input_run)
            print(f"Nacten input manifest z: {args.input_run}")
            
            # 2. Načti calls
            calls = self.load_calls(args.input_run)
            print(f"Nacteno {len(calls)} hovoru")
            
            if not calls:
                print("Zadne hovory k formatovani")
                return 0
            
            # 3. Aplikuj limit
            if args.limit:
                calls = calls[:args.limit]
                print(f"Omezeno na {len(calls)} hovoru")
            
            # 4. Formátuj do Markdown
            print(f"Formatuji {len(calls)} hovoru do Markdown...")
            results = self.format_calls_to_markdown(calls)
            
            # 5. Zapiš metriky
            runtime_s = time.time() - start_time
            metrics = self.write_metrics(results, runtime_s)
            
            # 6. Finalizuj manifest
            self.finalize_manifest(results, metrics)
            
            print(f"Formatovani dokonceno: {metrics['formatted_ok']} formatovano, {metrics['failed']} chyb")
            print(f"Markdown soubory: {self.markdown_dir}")
            
            return 0 if metrics['failed'] == 0 else 1
            
        except Exception as e:
            print(f"CHYBA: Kriticka chyba: {e}")
            
            # Zapiš error.json
            error_data = {
                "error": str(e),
                "type": type(e).__name__,
                "step_run_id": self.step_run_id
            }
            error_path = self.output_dir / "error.json"
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
            
            return 1


def main():
    """Hlavní CLI entry point."""
    parser = argparse.ArgumentParser(description="Format Markdown - převod do čitelných MD souborů")
    
    parser.add_argument('--input-run', required=True, help='Step run ID předchozího kroku (anonymize)')
    parser.add_argument('--run-id', help='Step run ID (jinak vygeneruje ULID)')
    parser.add_argument('--limit', type=int, help='Omez počet hovorů')
    parser.add_argument('--config', default='input/config.yaml', help='Cesta k konfiguračnímu souboru')
    
    args = parser.parse_args()
    
    # Urči step_run_id
    step_run_id = args.run_id or new_run_id()
    
    # Vytvoř runner
    config_path = Path(__file__).parent / args.config
    runner = FormatRunner(config_path, step_run_id)
    
    # Spusť
    return runner.run(args)


if __name__ == '__main__':
    sys.exit(main())
