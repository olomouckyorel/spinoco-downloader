#!/usr/bin/env python3
"""
steps/03_anonymize - Redigování PII z transkriptů.

Vytváří redigované varianty transcripts_recordings.jsonl a transcripts_calls.jsonl
s odstraněním/zakrytím PII pomocí deterministického tagování.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import yaml
import concurrent.futures
from threading import Lock

# Import common library
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common.lib import (
    new_run_id, is_valid_call_id,
    Manifest, create_manifest
)

from .anonymizer import (
    redact_recording, redact_call, load_transcript_file, save_transcript_file,
    save_vault_map, get_call_recordings, aggregate_pii_stats
)


class AnonymizeRunner:
    """Hlavní runner pro anonymizaci."""
    
    def __init__(self, config_path: Path, step_run_id: str, flow_run_id: Optional[str] = None):
        self.config_path = config_path
        self.step_run_id = step_run_id
        self.flow_run_id = flow_run_id
        
        # Načti konfiguraci
        self.config = self._load_config()
        
        # Nastav cesty
        self.step_dir = Path(__file__).parent
        self.output_dir = self.step_dir / "output" / "runs" / step_run_id
        self.data_dir = self.output_dir / "data"
        self.vault_map_dir = self.data_dir / self.config['output']['vault_map_dir']
        
        # Vytvoř adresáře
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vault_map_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializuj komponenty
        self.manifest = self._create_manifest()
        self.progress_lock = Lock()
    
    def _load_config(self) -> Dict[str, Any]:
        """Načte konfiguraci ze YAML souboru."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _create_manifest(self) -> Manifest:
        """Vytvoří manifest pro tento běh."""
        return create_manifest(
            schema="bh.v1.transcripts_redacted",
            schema_version="1.0.0",
            step_id="03_anonymize",
            run_mode=self.config.get('run_mode', 'incr'),
            flow_run_id=self.flow_run_id
        )
    
    def _update_progress(self, phase: str, pct: float, msg: str, eta_s: Optional[float] = None):
        """Aktualizuje progress.json."""
        progress_data = {
            "phase": phase,
            "pct": round(pct, 1),
            "msg": msg,
            "eta_s": eta_s,
            "updated_at_utc": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        with self.progress_lock:
            progress_path = self.output_dir / "progress.json"
            with open(progress_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
    
    def load_input_manifest(self, input_run_id: str) -> Dict[str, Any]:
        """Načte manifest z předchozího kroku."""
        input_run_root = Path(self.config['io']['input_run_root'])
        input_manifest_path = input_run_root / input_run_id / "manifest.json"
        
        if not input_manifest_path.exists():
            raise ValueError(f"Input manifest neexistuje: {input_manifest_path}")
        
        with open(input_manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_transcripts(self, input_run_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Načte transkripty z předchozího kroku."""
        input_run_root = Path(self.config['io']['input_run_root'])
        input_data_dir = input_run_root / input_run_id / "data"
        
        # Načti recording-level transkripty
        recordings_path = input_data_dir / "transcripts_recordings.jsonl"
        if not recordings_path.exists():
            raise ValueError(f"Recording transkripty neexistují: {recordings_path}")
        
        recordings = load_transcript_file(recordings_path)
        
        # Načti call-level transkripty
        calls_path = input_data_dir / "transcripts_calls.jsonl"
        if not calls_path.exists():
            raise ValueError(f"Call transkripty neexistují: {calls_path}")
        
        calls = load_transcript_file(calls_path)
        
        return recordings, calls
    
    def process_call(self, call: Dict[str, Any], recordings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Zpracuje jeden call s jeho recordingy."""
        call_id = call['call_id']
        
        try:
            # Najdi všechny recordingy pro tento call
            call_recordings = get_call_recordings(recordings, call_id)
            
            if not call_recordings:
                raise ValueError(f"Žádné recordingy pro call {call_id}")
            
            # Vytvoř kontext pro deterministické tagování
            context = {}
            
            # Rediguj všechny recordingy
            redacted_recordings = []
            for recording in call_recordings:
                redacted_recording = redact_recording(recording, self.config['anonymize'], context)
                redacted_recordings.append(redacted_recording)
            
            # Rediguj call-level transkript
            redacted_call, vault_map = redact_call(call, self.config['anonymize'])
            
            # Ulož vault map pokud je povoleno
            if self.config['anonymize'].get('make_vault_map', True):
                vault_map_path = self.vault_map_dir / f"{call_id}.json"
                save_vault_map(vault_map, vault_map_path)
            
            return {
                'success': True,
                'call_id': call_id,
                'redacted_call': redacted_call,
                'redacted_recordings': redacted_recordings,
                'vault_map': vault_map,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'call_id': call_id,
                'redacted_call': None,
                'redacted_recordings': [],
                'vault_map': {},
                'error': str(e)
            }
    
    def process_calls(self, calls: List[Dict[str, Any]], recordings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Zpracuje všechny calls paralelně."""
        self._update_progress("anonymization", 0.0, f"Rediguji {len(calls)} hovorů...")
        
        results = {
            'successful': [],
            'failed': [],
            'total_recordings': 0,
            'total_replacements': 0,
            'pii_counts': {}
        }
        
        def process_single(call: Dict[str, Any]) -> Dict[str, Any]:
            return self.process_call(call, recordings)
        
        # Paralelní zpracování
        max_parallel = self.config['io']['max_parallel']
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_call = {
                executor.submit(process_single, call): call 
                for call in calls
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_call):
                result = future.result()
                
                if result['success']:
                    results['successful'].append(result)
                    results['total_recordings'] += len(result['redacted_recordings'])
                    
                    # Agreguj PII stats
                    call_pii_stats = result['redacted_call'].get('pii_stats', {})
                    results['total_replacements'] += call_pii_stats.get('total_replacements', 0)
                    
                    for pii_type, count in call_pii_stats.get('by_type', {}).items():
                        results['pii_counts'][pii_type] = results['pii_counts'].get(pii_type, 0) + count
                else:
                    results['failed'].append(result)
                
                completed += 1
                pct = (completed / len(calls)) * 100
                self._update_progress("anonymization", pct, f"Zpracováno {completed}/{len(calls)} hovorů")
        
        return results
    
    def write_redacted_transcripts(self, results: Dict[str, Any]):
        """Zapíše redigované transkripty do JSONL souborů."""
        self._update_progress("output", 0.0, "Zapisuji redigované transkripty...")
        
        # Recording-level transkripty
        all_recordings = []
        for result in results['successful']:
            all_recordings.extend(result['redacted_recordings'])
        
        recordings_path = self.data_dir / self.config['output']['transcripts_recordings_redacted']
        save_transcript_file(all_recordings, recordings_path)
        
        # Call-level transkripty
        all_calls = [result['redacted_call'] for result in results['successful']]
        calls_path = self.data_dir / self.config['output']['transcripts_calls_redacted']
        save_transcript_file(all_calls, calls_path)
        
        self._update_progress("output", 100.0, "Redigované transkripty zapsány")
    
    def write_metrics(self, results: Dict[str, Any], runtime_s: float):
        """Zapíše metriky do metrics.json."""
        metrics = {
            "calls_total": len(results['successful']) + len(results['failed']),
            "calls_redacted": len(results['successful']),
            "calls_failed": len(results['failed']),
            "recordings_total": results['total_recordings'],
            "total_replacements": results['total_replacements'],
            "pii_counts": results['pii_counts'],
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
            primary=self.config['output']['transcripts_recordings_redacted'],
            call_level=self.config['output']['transcripts_calls_redacted']
        )
        
        # Nastav counts
        self.manifest.set_counts(
            calls=metrics['calls_total'],
            redacted=metrics['calls_redacted'],
            failed=metrics['calls_failed'],
            recordings=metrics['recordings_total'],
            replacements=metrics['total_replacements']
        )
        
        # Nastav metriky
        self.manifest.merge_metrics(
            throughput_calls_per_min=metrics['throughput_calls_per_min']
        )
        
        # Přidej PII counts jako metriky
        for pii_type, count in metrics['pii_counts'].items():
            self.manifest.merge_metrics(**{f"pii_{pii_type.lower()}": count})
        
        # Přidej chyby pokud jsou
        for failed in results['failed']:
            self.manifest.add_error(
                unit_id=failed['call_id'],
                error_key=failed['error'],
                message=f"Anonymization failed: {failed['error']}"
            )
        
        # Finalizuj podle výsledku
        if results['failed']:
            self.manifest.finalize_error(partial=True)
            
            # Zapiš error.json
            error_data = {
                "failed_ids": [f['call_id'] for f in results['failed']],
                "reason": "Some calls failed to anonymize",
                "retry_command": f"--only {','.join([f['call_id'] for f in results['failed']])}"
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
        """Hlavní běh anonymizace."""
        start_time = time.time()
        
        try:
            # 1. Načti input manifest a transkripty
            input_manifest = self.load_input_manifest(args.input_run)
            recordings, calls = self.load_transcripts(args.input_run)
            
            if not calls:
                print("Žádné hovory k redigování")
                return 0
            
            # 2. Filtruj calls podle --only/--limit
            filtered_calls = calls
            
            if args.only:
                # Filtruj podle --only
                only_ids = set(args.only.split(','))
                filtered_calls = [c for c in calls if c['call_id'] in only_ids]
            
            if args.limit:
                filtered_calls = filtered_calls[:args.limit]
            
            if not filtered_calls:
                print("Žádné hovory k redigování (filtrování)")
                return 0
            
            # 3. Zpracuj calls
            results = self.process_calls(filtered_calls, recordings)
            
            # 4. Zapiš redigované transkripty
            self.write_redacted_transcripts(results)
            
            # 5. Zapiš metriky
            runtime_s = time.time() - start_time
            metrics = self.write_metrics(results, runtime_s)
            
            # 6. Finalizuj manifest
            self.finalize_manifest(results, metrics)
            
            print(f"✅ Anonymizace dokončena: {metrics['calls_redacted']} redigováno, {metrics['calls_failed']} chyb")
            print(f"   PII náhrady: {metrics['total_replacements']} ({metrics['pii_counts']})")
            return 0 if metrics['calls_failed'] == 0 else 1
            
        except Exception as e:
            print(f"❌ Kritická chyba: {e}")
            
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
    parser = argparse.ArgumentParser(description="Anonymizer - redigování PII z transkriptů")
    
    parser.add_argument('--mode', choices=['backfill', 'incr', 'dry'], default='incr',
                       help='Režim běhu (default: incr)')
    parser.add_argument('--input-run', required=True, help='Step run ID předchozího kroku')
    parser.add_argument('--run-id', help='Step run ID (jinak vygeneruje ULID)')
    parser.add_argument('--only', help='Cílený retry - comma-separated call_ids')
    parser.add_argument('--limit', type=int, help='Omez počet hovorů')
    parser.add_argument('--config', default='input/config.example.yaml',
                       help='Cesta k konfiguračnímu souboru')
    
    args = parser.parse_args()
    
    # Urči step_run_id
    step_run_id = args.run_id or new_run_id()
    
    # Urči flow_run_id z ENV
    flow_run_id = None  # TODO: načti z ENV nebo Prefect
    
    # Vytvoř runner
    config_path = Path(__file__).parent / args.config
    runner = AnonymizeRunner(config_path, step_run_id, flow_run_id)
    
    # Spusť
    return runner.run(args)


if __name__ == '__main__':
    sys.exit(main())
