#!/usr/bin/env python3
"""
steps/01_ingest_spinoco - Stahování metadata hovorů a nahrávek ze Spinoco.

CLI pro ingest a download s idempotencí, partial-fail a manifest/metrics.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import yaml
import concurrent.futures
from threading import Lock

# Import common library
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common.lib import (
    new_run_id, call_id_from_spinoco, make_recording_ids,
    normalize_call_task, build_recordings_metadata, spinoco_to_internal,
    State, Manifest, create_manifest
)

from client import SpinocoClient, FakeSpinocoClient


def now_utc_iso() -> str:
    """Vrátí aktuální UTC čas ve formátu ISO."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


def fetch_calls_and_recordings(client, since: Optional[str] = None, limit: Optional[int] = None):
    """
    Načte hovory a nahrávky v main threadu pomocí asyncio.run().
    Vrátí hotové Python struktury (žádný async generator).
    """
    import asyncio
    
    async def _run():
        calls = []
        recordings_by_call = {}
        
        # Načti hovory
        async for call_task in client.client.get_completed_calls_with_recordings():
            if limit and len(calls) >= limit:
                break
                
            # Konvertuj CallTask na dict
            task_dict = {
                'id': call_task.id,
                'lastUpdate': call_task.lastUpdate,
                'tpe': call_task.tpe,
                'result': call_task.result,
                'detail': call_task.detail,
                'hashTags': call_task.hashTags,
                'owner': call_task.owner,
                'assignee': call_task.assignee
            }
            
            # Filtruj podle 'since' pokud je zadáno
            if since:
                from datetime import datetime
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                since_ms = int(since_dt.timestamp() * 1000)
                if task_dict.get('lastUpdate', 0) < since_ms:
                    continue
            
            calls.append(task_dict)
            
            # Načti nahrávky pro tento hovor
            recordings = client.client.extract_available_recordings(call_task)
            recordings_by_call[call_task.id] = [recording.dict() for recording in recordings]
        
        return calls, recordings_by_call
    
    return asyncio.run(_run())


class IngestRunner:
    """Hlavní runner pro ingest proces."""
    
    def __init__(self, config_path: Path, step_run_id: str, flow_run_id: Optional[str] = None):
        self.config_path = config_path
        self.step_run_id = step_run_id
        self.flow_run_id = flow_run_id
        
        # Načti konfiguraci
        self.config = self._load_config()
        
        # Nastav cesty
        self.step_dir = Path(__file__).parent
        self.state_path = self.step_dir / "state" / "processed.sqlite"
        self.output_dir = self.step_dir / "output" / "runs" / step_run_id
        self.data_dir = self.output_dir / "data"
        self.audio_dir = self.data_dir / "audio"
        
        # Vytvoř adresáře
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializuj komponenty
        self.state = State(str(self.state_path))
        self.manifest = self._create_manifest()
        self.progress_lock = Lock()
        
        # Nastav client (fake pro testy, reálný pro produkci)
        if self.config.get('test_mode', False):
            fixtures_dir = self.step_dir / "input" / "fixtures"
            self.client = FakeSpinocoClient(fixtures_dir)
        else:
            auth = self.config['auth']
            self.client = SpinocoClient(
                api_base_url=auth['api_base_url'],
                token=auth['token'],
                page_size=self.config['fetch']['page_size']
            )
    
    def _load_config(self) -> Dict[str, Any]:
        """Načte konfiguraci ze YAML souboru."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _create_manifest(self) -> Manifest:
        """Vytvoří manifest pro tento běh."""
        return create_manifest(
            schema="bh.v1.raw_audio",
            schema_version="1.0.0",
            step_id="01_ingest_spinoco",
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
    
    def _validate_ogg_file(self, file_path: Path) -> bool:
        """Validuje že soubor je platný OGG."""
        if not self.config['download']['validate_ogg_header']:
            return True
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                return header == b'OggS'
        except Exception:
            return False
    
    def fetch_calls(self, since: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Načte hovory ze Spinoco API pomocí async fetch v main threadu."""
        self._update_progress("fetch_calls", 0.0, "Načítám hovory ze Spinoco API...")
        
        # Použij async fetch v main threadu
        calls_data, recordings_by_call = fetch_calls_and_recordings(self.client, since, limit)
        
        calls = []
        for call_task in calls_data:
            print(f"Načten hovor: {call_task['id']} (lastUpdate: {call_task['lastUpdate']})")
            
            # Normalizuj call task
            normalized_call = normalize_call_task(call_task)
            
            # Upsert do state
            self.state.upsert_call(
                spinoco_call_guid=call_task['id'],
                call_id=normalized_call['call_id'],
                last_update_ms=call_task['lastUpdate'],
                seen_at_utc=normalized_call['call_ts_utc']
            )
            
            calls.append({
                'call_task': call_task,
                'normalized_call': normalized_call,
                'recordings': recordings_by_call.get(call_task['id'], [])
            })
        
        print(f"Celkem načteno {len(calls)} hovorů ze Spinoco API")
        
        self._update_progress("fetch_calls", 100.0, f"Načteno {len(calls)} hovorů")
        return calls
    
    def fetch_recordings(self, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Zpracuje metadata nahrávek pro všechny hovory (už načtené v fetch_calls)."""
        self._update_progress("fetch_recordings", 0.0, "Zpracovávám metadata nahrávek...")
        
        all_recordings = []
        
        for i, call_data in enumerate(calls):
            call_task = call_data['call_task']
            normalized_call = call_data['normalized_call']
            recordings = call_data.get('recordings', [])
            
            print(f"Hovor {call_task['id']}: nalezeno {len(recordings)} nahrávek")
            
            # Debug: vypiš strukturu detail
            detail = call_task.get('detail', {})
            print(f"  Detail __tpe: {detail.get('__tpe')}")
            print(f"  Recordings keys: {list(detail.get('recordings', {}).keys())}")
            
            # Normalizuj nahrávky
            normalized_recordings = build_recordings_metadata(normalized_call, recordings)
            
            # Upsert každou nahrávku do state
            for recording in recordings:
                normalized_rec = next(
                    (nr for nr in normalized_recordings if nr['spinoco_recording_id'] == recording['id']),
                    None
                )
                
                if normalized_rec:
                    self.state.upsert_recording(
                        spinoco_recording_id=recording['id'],
                        spinoco_call_guid=call_task['id'],
                        recording_id=normalized_rec['recording_id'],
                        recording_date_ms=recording['date'],
                        size_bytes=None,  # Zjistíme při stahování
                        content_etag=None
                    )
            
            all_recordings.extend(normalized_recordings)
            
            # Aktualizuj progress
            pct = ((i + 1) / len(calls)) * 100
            self._update_progress("fetch_recordings", pct, f"Zpracováno {i+1}/{len(calls)} hovorů")
        
        self._update_progress("fetch_recordings", 100.0, f"Načteno {len(all_recordings)} nahrávek")
        return all_recordings
    
    def download_recordings(self, recording_ids: List[str]) -> Dict[str, Any]:
        """Stáhne nahrávky paralelně."""
        self._update_progress("download", 0.0, f"Stahuji {len(recording_ids)} nahrávek...")
        
        results = {
            'downloaded': [],
            'failed': [],
            'total_bytes': 0
        }
        
        def _download_worker(recording_id: str) -> tuple:
            """
            Worker funkce - jen stahuje OGG a vrací výsledek (bez DB operací).
            Vrací: (status, recording_id, size_bytes, etag, error)
            """
            temp_path = self.audio_dir / f"{recording_id}{self.config['download']['temp_suffix']}"
            final_path = self.audio_dir / f"{recording_id}.ogg"
            
            try:
                # Stáhni do temp souboru
                size_bytes = self.client.download_recording(recording_id, temp_path)
                
                # Validuj OGG
                if not self._validate_ogg_file(temp_path):
                    temp_path.unlink(missing_ok=True)
                    return ("fail", recording_id, None, None, "invalid_ogg_header")
                
                # Přesuň na finální název
                temp_path.rename(final_path)
                
                return ("ok", recording_id, size_bytes, None, None)
                
            except Exception as e:
                temp_path.unlink(missing_ok=True)
                return ("fail", recording_id, None, None, f"{type(e).__name__}:{e}")
        
        # Paralelní stahování
        concurrency = self.config['download']['concurrency']
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_recording = {
                executor.submit(_download_worker, recording_id): recording_id 
                for recording_id in recording_ids
            }
            
            completed = 0
            ok = 0
            failed = 0
            
            for future in concurrent.futures.as_completed(future_to_recording):
                status, rec_id, size_bytes, etag, error = future.result()
                
                if status == "ok":
                    # DB operace v main threadu
                    self.state.mark_downloaded(
                        spinoco_recording_id=rec_id,
                        size_bytes=size_bytes,
                        content_etag=etag,
                        processed_at_utc=now_utc_iso()
                    )
                    
                    results['downloaded'].append({
                        'recording_id': rec_id,
                        'success': True,
                        'error': None,
                        'size_bytes': size_bytes
                    })
                    results['total_bytes'] += size_bytes
                    ok += 1
                else:
                    # DB operace v main threadu
                    retry_count = self.state.mark_failed_transient(
                        spinoco_recording_id=rec_id,
                        error_key=f"download_error: {error}",
                        failed_at_utc=now_utc_iso()
                    )
                    
                    if retry_count >= self.config['retry']['max_retry']:
                        self.state.mark_failed_permanent(
                            spinoco_recording_id=rec_id,
                            error_key="max_retry_exceeded",
                            failed_at_utc=now_utc_iso()
                        )
                    
                    results['failed'].append({
                        'recording_id': rec_id,
                        'success': False,
                        'error': error,
                        'size_bytes': 0
                    })
                    failed += 1
                
                completed += 1
                pct = (completed / len(recording_ids)) * 100
                self._update_progress("download", pct, f"Staženo {completed}/{len(recording_ids)} nahrávek (OK: {ok}, FAIL: {failed})")
        
        return results
    
    def write_snapshots(self, calls: List[Dict[str, Any]], recordings: List[Dict[str, Any]]):
        """Zapíše metadata snapshots do JSONL souborů."""
        self._update_progress("snapshots", 0.0, "Zapisuji metadata snapshots...")
        
        # Metadata call tasks
        calls_path = self.data_dir / self.config['output']['metadata_calls']
        with open(calls_path, 'w', encoding='utf-8') as f:
            for call_data in calls:
                json.dump(call_data['normalized_call'], f, ensure_ascii=False)
                f.write('\n')
        
        # Metadata recordings
        recordings_path = self.data_dir / self.config['output']['metadata_recordings']
        with open(recordings_path, 'w', encoding='utf-8') as f:
            for recording in recordings:
                json.dump(recording, f, ensure_ascii=False)
                f.write('\n')
        
        self._update_progress("snapshots", 100.0, "Metadata snapshots zapsány")
    
    def write_metrics(self, download_results: Dict[str, Any], runtime_s: float):
        """Zapíše metriky do metrics.json."""
        stats = self.state.get_stats()
        
        metrics = {
            "calls": stats['total_calls'],
            "recordings_total": len(download_results['downloaded']) + len(download_results['failed']),
            "downloaded_ok": len(download_results['downloaded']),
            "failed": len(download_results['failed']),
            "bytes_downloaded": download_results['total_bytes'],
            "runtime_s": runtime_s,
            "throughput_mbps": (download_results['total_bytes'] / (1024 * 1024)) / runtime_s if runtime_s > 0 else 0
        }
        
        metrics_path = self.output_dir / "metrics.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        return metrics
    
    def finalize_manifest(self, calls: List[Dict[str, Any]], recordings: List[Dict[str, Any]], 
                         download_results: Dict[str, Any], metrics: Dict[str, Any]):
        """Finalizuje manifest."""
        # Přidej input refs
        for recording in recordings:
            self.manifest.add_input_ref("recording_id", recording['recording_id'])
        
        # Nastav outputs
        self.manifest.set_outputs(
            primary=self.config['output']['metadata_recordings'],
            calls=self.config['output']['metadata_calls'],
            audio_dir=self.config['output']['audio_dir']
        )
        
        # Nastav counts
        self.manifest.set_counts(
            calls=metrics['calls'],
            recordings=metrics['recordings_total'],
            downloaded=metrics['downloaded_ok'],
            failed=metrics['failed']
        )
        
        # Nastav metriky
        self.manifest.merge_metrics(
            bytes_downloaded=metrics['bytes_downloaded'],
            throughput_mbps=metrics['throughput_mbps']
        )
        
        # Přidej chyby pokud jsou
        for failed in download_results['failed']:
            self.manifest.add_error(
                unit_id=failed['recording_id'],
                error_key=failed['error'],
                message=f"Download failed: {failed['error']}"
            )
        
        # Finalizuj podle výsledku
        if download_results['failed']:
            self.manifest.finalize_error(partial=True)
            
            # Zapiš error.json
            error_data = {
                "failed_ids": [f['recording_id'] for f in download_results['failed']],
                "reason": "Some recordings failed to download",
                "retry_command": f"--only {','.join([f['recording_id'] for f in download_results['failed']])}"
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
        """Hlavní běh ingest procesu."""
        start_time = time.time()
        
        try:
            # 1. Fetch calls
            since = args.since or self.config['fetch'].get('since')
            calls = self.fetch_calls(since=since, limit=args.limit)
            
            if not calls:
                print("Žádné hovory k zpracování")
                return 0
            
            # 2. Fetch recordings
            recordings = self.fetch_recordings(calls)
            
            if not recordings:
                print("Žádné nahrávky k stažení")
                return 0
            
            # 3. Urči TODO pro download
            todo_recordings = self.state.list_todo_for_download(max_retry=args.max_retry)
            
            if args.only:
                # Filtruj podle --only
                only_ids = set(args.only.split(','))
                todo_recordings = [r for r in todo_recordings if r['recording_id'] in only_ids]
            
            if args.limit:
                todo_recordings = todo_recordings[:args.limit]
            
            if not todo_recordings:
                print("Žádné nahrávky k stažení (všechny již staženy)")
                return 0
            
            # 4. Download recordings
            recording_ids = [r['recording_id'] for r in todo_recordings]
            download_results = self.download_recordings(recording_ids)
            
            # 5. Write snapshots
            self.write_snapshots(calls, recordings)
            
            # 6. Write metrics
            runtime_s = time.time() - start_time
            metrics = self.write_metrics(download_results, runtime_s)
            
            # 7. Finalize manifest
            self.finalize_manifest(calls, recordings, download_results, metrics)
            
            print(f"✅ Ingest dokončen: {metrics['downloaded_ok']} staženo, {metrics['failed']} chyb")
            return 0 if metrics['failed'] == 0 else 1
            
        except Exception as e:
            print(f"ERROR: Kritická chyba: {e}")
            
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
        
        finally:
            self.state.close()


def main():
    """Hlavní CLI entry point."""
    parser = argparse.ArgumentParser(description="Spinoco ingest - stahování hovorů a nahrávek")
    
    parser.add_argument('--mode', choices=['backfill', 'incr', 'dry'], default='incr',
                       help='Režim běhu (default: incr)')
    parser.add_argument('--run-id', help='Step run ID (jinak vygeneruje ULID)')
    parser.add_argument('--since', help='ISO timestamp pro backfill (např. 2024-01-01T00:00:00Z)')
    parser.add_argument('--only', help='Cílený retry - comma-separated recording_ids')
    parser.add_argument('--max-retry', type=int, default=3, help='Maximální počet retry')
    parser.add_argument('--limit', type=int, help='Omez počet recordingů ke stažení')
    parser.add_argument('--config', default='input/config.example.yaml',
                       help='Cesta k konfiguračnímu souboru')
    
    args = parser.parse_args()
    
    # Urči step_run_id
    step_run_id = args.run_id or new_run_id()
    
    # Urči flow_run_id z ENV
    flow_run_id = None  # TODO: načti z ENV nebo Prefect
    
    # Vytvoř runner
    config_path = Path(__file__).parent / args.config
    runner = IngestRunner(config_path, step_run_id, flow_run_id)
    
    # Spusť
    return runner.run(args)


if __name__ == '__main__':
    sys.exit(main())
