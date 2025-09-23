#!/usr/bin/env python3
"""
steps/02_transcribe_asr_adapter - Adaptace existující Whisper transkripce.

Orchestruje import/spuštění + normalizaci do našeho standardizovaného formátu.
"""

import argparse
import json
import sys
import time
import subprocess
import glob
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import yaml
import concurrent.futures
from threading import Lock
import sqlite3

# Import common library
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common.lib import (
    new_run_id, is_valid_call_id, is_valid_run_id,
    State, Manifest, create_manifest
)

from .adapter import normalize_recording, normalize_call_level, load_transcript_json, find_transcript_file


def now_utc_iso() -> str:
    """Vrátí aktuální UTC čas ve formátu ISO."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


class TranscribeState:
    """State management pro transkripce."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._migrate_if_needed()
    
    def _connect(self):
        """Připojí se k SQLite databázi."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.commit()
    
    def _migrate_if_needed(self):
        """Aplikuje migrace pokud je potřeba."""
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        self.conn.commit()
        
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'schema_version';")
        current_version = int(cursor.fetchone()[0]) if cursor.fetchone() else 0
        
        if current_version < 1:
            self._apply_migrations(0)
            cursor.execute("REPLACE INTO schema_meta (key, value) VALUES ('schema_version', '1');")
            self.conn.commit()
    
    def _apply_migrations(self, from_version: int):
        """Aplikuje migrace."""
        if from_version < 1:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS transcripts(
                  recording_id           TEXT PRIMARY KEY,
                  call_id                TEXT NOT NULL,
                  status                 TEXT NOT NULL DEFAULT 'pending',
                  retry_count            INTEGER NOT NULL DEFAULT 0,
                  last_error             TEXT,
                  last_error_at_utc      TEXT,
                  last_processed_at_utc  TEXT,
                  asr_provider           TEXT NOT NULL DEFAULT 'existing',
                  asr_settings_hash      TEXT,
                  transcript_hash        TEXT
                );
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_call ON transcripts(call_id);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_status ON transcripts(status);")
            self.conn.commit()
    
    def close(self):
        """Zavře připojení."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def upsert_transcript(self, recording_id: str, call_id: str, asr_settings_hash: str, transcript_hash: str) -> str:
        """Upsert transcript záznam."""
        with self.conn:
            cursor = self.conn.execute("SELECT * FROM transcripts WHERE recording_id = ?;", (recording_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Zkontroluj změny
                if (existing['asr_settings_hash'] != asr_settings_hash or 
                    existing['transcript_hash'] != transcript_hash):
                    self.conn.execute("""
                        UPDATE transcripts SET
                            call_id = ?, status = 'pending', retry_count = 0,
                            asr_settings_hash = ?, transcript_hash = ?,
                            last_error = NULL, last_error_at_utc = NULL, last_processed_at_utc = NULL
                        WHERE recording_id = ?;
                    """, (call_id, asr_settings_hash, transcript_hash, recording_id))
                    return 'updated'
                return 'unchanged'
            else:
                self.conn.execute("""
                    INSERT INTO transcripts (recording_id, call_id, asr_settings_hash, transcript_hash)
                    VALUES (?, ?, ?, ?);
                """, (recording_id, call_id, asr_settings_hash, transcript_hash))
                return 'inserted'
    
    def mark_ok(self, recording_id: str, processed_at_utc: str) -> None:
        """Označí transcript jako úspěšný."""
        with self.conn:
            self.conn.execute("""
                UPDATE transcripts SET
                    status = 'ok', last_processed_at_utc = ?, retry_count = 0,
                    last_error = NULL, last_error_at_utc = NULL
                WHERE recording_id = ?;
            """, (processed_at_utc, recording_id))
    
    def mark_failed_transient(self, recording_id: str, error_key: str, failed_at_utc: str) -> int:
        """Označí transcript jako selhaný (transient)."""
        with self.conn:
            self.conn.execute("""
                UPDATE transcripts SET
                    status = 'failed-transient', retry_count = retry_count + 1,
                    last_error = ?, last_error_at_utc = ?
                WHERE recording_id = ?;
            """, (error_key, failed_at_utc, recording_id))
            cursor = self.conn.execute("SELECT retry_count FROM transcripts WHERE recording_id = ?;", (recording_id,))
            return cursor.fetchone()['retry_count']
    
    def mark_failed_permanent(self, recording_id: str, error_key: str, failed_at_utc: str) -> None:
        """Označí transcript jako selhaný (permanent)."""
        with self.conn:
            self.conn.execute("""
                UPDATE transcripts SET
                    status = 'failed-permanent', last_error = ?, last_error_at_utc = ?
                WHERE recording_id = ?;
            """, (error_key, failed_at_utc, recording_id))
    
    def list_todo_for_transcription(self, max_retry: int = 2, limit: Optional[int] = None) -> List[Dict]:
        """Vrátí seznam recordingů k transkripci."""
        query = """
            SELECT * FROM transcripts
            WHERE (status = 'pending' OR (status = 'failed-transient' AND retry_count < ?))
            ORDER BY recording_id ASC
        """
        params = [max_retry]
        if limit is not None:
            query += f" LIMIT {limit}"
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Vrátí statistiky."""
        cursor = self.conn.execute("SELECT status, COUNT(*) as count FROM transcripts GROUP BY status;")
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM transcripts;")
        total_transcripts = cursor.fetchone()['count']
        
        return {
            "total_transcripts": total_transcripts,
            "status_counts": status_counts,
            "db_path": self.db_path
        }


class TranscribeRunner:
    """Hlavní runner pro transkripci."""
    
    def __init__(self, config_path: Path, step_run_id: str, flow_run_id: Optional[str] = None):
        self.config_path = config_path
        self.step_run_id = step_run_id
        self.flow_run_id = flow_run_id
        
        # Načti konfiguraci
        self.config = self._load_config()
        
        # Nastav cesty
        self.step_dir = Path(__file__).parent
        self.state_path = self.step_dir / "state" / "transcribed.sqlite"
        self.output_dir = self.step_dir / "output" / "runs" / step_run_id
        self.data_dir = self.output_dir / "data"
        
        # Vytvoř adresáře
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializuj komponenty
        self.state = TranscribeState(str(self.state_path))
        self.manifest = self._create_manifest()
        self.progress_lock = Lock()
    
    def _load_config(self) -> Dict[str, Any]:
        """Načte konfiguraci ze YAML souboru."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _create_manifest(self) -> Manifest:
        """Vytvoří manifest pro tento běh."""
        return create_manifest(
            schema="bh.v1.transcripts",
            schema_version="1.0.0",
            step_id="02_transcribe_asr_adapter",
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
    
    def load_recordings_metadata(self, input_run_id: str) -> List[Dict[str, Any]]:
        """Načte metadata nahrávek z předchozího kroku."""
        input_run_root = Path(self.config['io']['input_run_root'])
        metadata_path = input_run_root / input_run_id / "data" / "metadata_recordings.jsonl"
        
        if not metadata_path.exists():
            raise ValueError(f"Metadata recordings neexistuje: {metadata_path}")
        
        recordings = []
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    recordings.append(json.loads(line))
        
        return recordings
    
    def run_transcriber(self, audio_path: Path, output_dir: Path) -> Path:
        """Spustí externí transcriber."""
        asr_config = self.config['asr']
        run_cmd = asr_config['run_cmd']
        
        # Nahraď placeholdery
        cmd = run_cmd.format(
            python=sys.executable,  # Použij aktuální Python executable
            audio=str(audio_path),
            out_dir=str(output_dir)
        )
        
        # Spusť příkaz
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Transcriber selhal: {result.stderr}")
        
        # Najdi výstupní JSON
        outputs_glob = asr_config['outputs_glob']
        matches = list(output_dir.glob(outputs_glob))
        
        if not matches:
            raise RuntimeError(f"Nenalezen výstupní JSON podle pattern: {outputs_glob}")
        
        return matches[0]  # Vezmi první match
    
    def process_recording(self, recording: Dict[str, Any], input_run_id: str) -> Dict[str, Any]:
        """Zpracuje jednu nahrávku."""
        recording_id = recording['recording_id']
        call_id = recording['call_id']
        
        # Najdi audio soubor
        input_run_root = Path(self.config['io']['input_run_root'])
        audio_path = input_run_root / input_run_id / "data" / "audio" / f"{recording_id}.ogg"
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio soubor neexistuje: {audio_path}")
        
        # Urči výstupní adresář
        temp_output_dir = self.data_dir / "temp" / recording_id
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Spusť transcriber nebo načti existující JSON
            asr_config = self.config['asr']
            
            if asr_config['mode'] == 'run':
                transcript_path = self.run_transcriber(audio_path, temp_output_dir)
            elif asr_config['mode'] == 'import':
                # Najdi existující JSON
                base_path = Path(asr_config.get('import_base_path', '.'))
                transcript_path = find_transcript_file(base_path, recording_id, asr_config['outputs_glob'])
                if not transcript_path:
                    raise FileNotFoundError(f"Nenalezen transcript pro {recording_id}")
            else:
                raise ValueError(f"Neplatný ASR mode: {asr_config['mode']}")
            
            # Načti a normalizuj transcript
            transcript_json = load_transcript_json(transcript_path)
            audio_rel_path = f"audio/{recording_id}.ogg"
            
            normalized = normalize_recording(transcript_json, recording_id, call_id, audio_rel_path)
            
            return {
                'success': True,
                'recording_id': recording_id,
                'transcript': normalized,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'recording_id': recording_id,
                'transcript': None,
                'error': str(e)
            }
    
    def process_recordings(self, recordings: List[Dict[str, Any]], input_run_id: str) -> Dict[str, Any]:
        """Zpracuje všechny nahrávky paralelně."""
        self._update_progress("transcription", 0.0, f"Zpracovávám {len(recordings)} nahrávek...")
        
        results = {
            'successful': [],
            'failed': [],
            'total_segments': 0
        }
        
        def _transcribe_worker(job: Dict[str, Any]) -> tuple:
            """
            Worker funkce - jen ASR a normalizace (bez DB operací).
            Vrací: (status, recording_id, normalized_transcript, error)
            """
            recording_id = job['recording_id']
            call_id = job['call_id']
            
            try:
                # Najdi audio soubor
                input_run_root = Path(self.config['io']['input_run_root'])
                audio_path = input_run_root / input_run_id / "data" / "audio" / f"{recording_id}.ogg"
                
                if not audio_path.exists():
                    return ("fail", recording_id, None, "FileNotFoundError: Audio soubor neexistuje")
                
                # Urči výstupní adresář
                temp_output_dir = self.data_dir / "temp" / recording_id
                temp_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Spusť transcriber nebo načti existující JSON
                asr_config = self.config['asr']
                
                if asr_config['mode'] == 'run':
                    transcript_path = self.run_transcriber(audio_path, temp_output_dir)
                elif asr_config['mode'] == 'import':
                    # Najdi existující JSON
                    base_path = Path(asr_config.get('import_base_path', '.'))
                    transcript_path = find_transcript_file(base_path, recording_id, asr_config['outputs_glob'])
                    if not transcript_path:
                        return ("fail", recording_id, None, "FileNotFoundError: Nenalezen transcript")
                else:
                    return ("fail", recording_id, None, f"ValueError: Neplatný ASR mode: {asr_config['mode']}")
                
                # Načti a normalizuj transcript
                transcript_json = load_transcript_json(transcript_path)
                audio_rel_path = f"audio/{recording_id}.ogg"
                normalized_transcript = normalize_recording(transcript_json, recording_id, call_id, audio_rel_path)
                
                return ("ok", recording_id, normalized_transcript, None)
                
            except Exception as e:
                return ("fail", recording_id, None, f"{type(e).__name__}:{e}")
        
        # Paralelní zpracování
        max_parallel = self.config['io']['max_parallel']
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_recording = {
                executor.submit(_transcribe_worker, recording): recording 
                for recording in recordings
            }
            
            completed = 0
            ok = 0
            failed = 0
            
            for future in concurrent.futures.as_completed(future_to_recording):
                status, rec_id, normalized_transcript, error = future.result()
                
                if status == "ok":
                    # DB operace v main threadu
                    self.state.mark_transcribed(
                        recording_id=rec_id,
                        asr_model=self.config['asr']['provider'],
                        settings_hash="dummy_hash",  # TODO: implementovat hash
                        processed_at_utc=now_utc_iso()
                    )
                    
                    results['successful'].append({
                        'recording_id': rec_id,
                        'success': True,
                        'transcript': normalized_transcript,
                        'error': None
                    })
                    results['total_segments'] += normalized_transcript['metrics']['seg_count']
                    ok += 1
                else:
                    # DB operace v main threadu
                    retry_count = self.state.mark_failed_transient(
                        recording_id=rec_id,
                        error_key=f"asr_error: {error}",
                        failed_at_utc=now_utc_iso()
                    )
                    
                    if retry_count >= self.config['retry']['max_retry']:
                        self.state.mark_failed_permanent(
                            recording_id=rec_id,
                            error_key="max_retry_exceeded",
                            failed_at_utc=now_utc_iso()
                        )
                    
                    results['failed'].append({
                        'recording_id': rec_id,
                        'success': False,
                        'transcript': None,
                        'error': error
                    })
                    failed += 1
                
                completed += 1
                pct = (completed / len(recordings)) * 100
                self._update_progress("transcription", pct, f"Zpracováno {completed}/{len(recordings)} nahrávek (OK: {ok}, FAIL: {failed})")
        
        return results
    
    def write_transcripts(self, results: Dict[str, Any]):
        """Zapíše transkripty do JSONL souborů v main threadu."""
        self._update_progress("output", 0.0, "Zapisuji transkripty...")
        
        # Buffer pro call-level agregace
        call_buffer = {}
        
        # Recording-level transkripty
        recordings_path = self.data_dir / self.config['output']['transcripts_recordings']
        with open(recordings_path, 'w', encoding='utf-8') as f:
            for result in results['successful']:
                transcript = result['transcript']
                json.dump(transcript, f, ensure_ascii=False)
                f.write('\n')
                
                # Přidej do bufferu pro call-level agregaci
                call_id = transcript['call_id']
                if call_id not in call_buffer:
                    call_buffer[call_id] = []
                call_buffer[call_id].append(transcript)
        
        # Call-level agregace z bufferu
        calls_path = self.data_dir / self.config['output']['transcripts_calls']
        with open(calls_path, 'w', encoding='utf-8') as f:
            for call_id, recordings in call_buffer.items():
                call_transcript = normalize_call_level(recordings)
                json.dump(call_transcript, f, ensure_ascii=False)
                f.write('\n')
        
        self._update_progress("output", 100.0, "Transkripty zapsány")
    
    def write_metrics(self, results: Dict[str, Any], runtime_s: float):
        """Zapíše metriky do metrics.json."""
        metrics = {
            "recordings_total": len(results['successful']) + len(results['failed']),
            "transcribed_ok": len(results['successful']),
            "failed": len(results['failed']),
            "total_segments": results['total_segments'],
            "avg_segments_per_recording": results['total_segments'] / len(results['successful']) if results['successful'] else 0,
            "runtime_s": runtime_s,
            "throughput_records_per_min": len(results['successful']) / (runtime_s / 60) if runtime_s > 0 else 0
        }
        
        metrics_path = self.output_dir / "metrics.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        return metrics
    
    def finalize_manifest(self, results: Dict[str, Any], metrics: Dict[str, Any]):
        """Finalizuje manifest."""
        # Přidej input refs
        for result in results['successful']:
            self.manifest.add_input_ref("recording_id", result['recording_id'])
        
        # Nastav outputs
        self.manifest.set_outputs(
            primary=self.config['output']['transcripts_recordings'],
            call_level=self.config['output']['transcripts_calls']
        )
        
        # Nastav counts
        self.manifest.set_counts(
            recordings=metrics['recordings_total'],
            transcribed=metrics['transcribed_ok'],
            failed=metrics['failed'],
            segments=metrics['total_segments']
        )
        
        # Nastav metriky
        self.manifest.merge_metrics(
            avg_segments_per_recording=metrics['avg_segments_per_recording'],
            throughput_records_per_min=metrics['throughput_records_per_min']
        )
        
        # Přidej chyby pokud jsou
        for failed in results['failed']:
            self.manifest.add_error(
                unit_id=failed['recording_id'],
                error_key=failed['error'],
                message=f"Transcription failed: {failed['error']}"
            )
        
        # Finalizuj podle výsledku
        if results['failed']:
            self.manifest.finalize_error(partial=True)
            
            # Zapiš error.json
            error_data = {
                "failed_ids": [f['recording_id'] for f in results['failed']],
                "reason": "Some recordings failed to transcribe",
                "retry_command": f"--only {','.join([f['recording_id'] for f in results['failed']])}"
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
        """Hlavní běh transkripce."""
        start_time = time.time()
        
        try:
            # 1. Načti input manifest a metadata
            input_manifest = self.load_input_manifest(args.input_run)
            recordings_metadata = self.load_recordings_metadata(args.input_run)
            
            if not recordings_metadata:
                print("Žádné nahrávky k transkripci")
                return 0
            
            # 2. Urči TODO pro transkripci
            todo_recordings = self.state.list_todo_for_transcription(max_retry=args.max_retry)
            
            if args.only:
                # Filtruj podle --only
                only_ids = set(args.only.split(','))
                todo_recordings = [r for r in todo_recordings if r['recording_id'] in only_ids]
            
            if args.limit:
                todo_recordings = todo_recordings[:args.limit]
            
            if not todo_recordings:
                print("Žádné nahrávky k transkripci (všechny již zpracovány)")
                return 0
            
            # 3. Zpracuj nahrávky
            results = self.process_recordings(todo_recordings, args.input_run)
            
            # 4. Zapiš transkripty
            self.write_transcripts(results)
            
            # 5. Zapiš metriky
            runtime_s = time.time() - start_time
            metrics = self.write_metrics(results, runtime_s)
            
            # 6. Finalizuj manifest
            self.finalize_manifest(results, metrics)
            
            print(f"✅ Transkripce dokončena: {metrics['transcribed_ok']} zpracováno, {metrics['failed']} chyb")
            return 0 if metrics['failed'] == 0 else 1
            
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
        
        finally:
            self.state.close()


def main():
    """Hlavní CLI entry point."""
    parser = argparse.ArgumentParser(description="ASR Adapter - adaptace existující transkripce")
    
    parser.add_argument('--mode', choices=['backfill', 'incr', 'dry'], default='incr',
                       help='Režim běhu (default: incr)')
    parser.add_argument('--input-run', required=True, help='Step run ID předchozího kroku')
    parser.add_argument('--run-id', help='Step run ID (jinak vygeneruje ULID)')
    parser.add_argument('--only', help='Cílený retry - comma-separated recording_ids')
    parser.add_argument('--max-retry', type=int, default=2, help='Maximální počet retry')
    parser.add_argument('--limit', type=int, help='Omez počet recordingů')
    parser.add_argument('--config', default='input/config.example.yaml',
                       help='Cesta k konfiguračnímu souboru')
    
    args = parser.parse_args()
    
    # Urči step_run_id
    step_run_id = args.run_id or new_run_id()
    
    # Urči flow_run_id z ENV
    flow_run_id = None  # TODO: načti z ENV nebo Prefect
    
    # Vytvoř runner
    config_path = Path(__file__).parent / args.config
    runner = TranscribeRunner(config_path, step_run_id, flow_run_id)
    
    # Spusť
    return runner.run(args)


if __name__ == '__main__':
    sys.exit(main())
