"""
Integrační testy pro steps/02_transcribe_asr_adapter.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Přidej common library do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.lib import State, Manifest
from adapter import normalize_recording, normalize_call_level, load_transcript_json
from run import TranscribeRunner, TranscribeState


class TestAdapter:
    """Testy pro adapter funkce."""
    
    def test_normalize_recording(self):
        """Testuje normalizaci recording-level transkriptu."""
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
                    },
                    {
                        "id": 1,
                        "start": 5.2,
                        "end": 10.5,
                        "text": " o technické podpoře."
                    }
                ]
            },
            "metadata": {
                "filename": "test_recording.ogg",
                "duration": 10.5,
                "whisper_model": "large-v3",
                "device_used": "cpu",
                "beam_size": 5,
                "best_of": 5,
                "temperature": 0.0,
                "language": "cs",
                "processed_at": "2024-08-22T05:43:36Z"
            }
        }
        
        result = normalize_recording(
            transcript_json, 
            "20240822_054336_71da9579_p01", 
            "20240822_054336_71da9579",
            "audio/20240822_054336_71da9579_p01.ogg"
        )
        
        assert result['call_id'] == "20240822_054336_71da9579"
        assert result['recording_id'] == "20240822_054336_71da9579_p01"
        assert result['duration_s'] == 10.5
        assert result['lang'] == "cs"
        assert result['asr']['provider'] == "existing"
        assert result['asr']['model'] == "large-v3"
        assert result['asr']['device'] == "cpu"
        assert len(result['segments']) == 2
        assert result['segments'][0]['start'] == 0.0
        assert result['segments'][0]['end'] == 5.2
        assert result['text'] == "Testovací přepis hovoru o technické podpoře."
        assert result['metrics']['seg_count'] == 2
        assert result['source']['audio_path'] == "audio/20240822_054336_71da9579_p01.ogg"
        assert 'asr_settings_hash' in result['processing']
        assert 'transcript_hash' in result['processing']
    
    def test_normalize_call_level(self):
        """Testuje agregaci do call-level transkriptu."""
        recording_transcripts = [
            {
                'call_id': '20240822_054336_71da9579',
                'recording_id': '20240822_054336_71da9579_p01',
                'duration_s': 10.5,
                'lang': 'cs',
                'segments': [
                    {'start': 0.0, 'end': 5.2, 'text': 'První část'},
                    {'start': 5.2, 'end': 10.5, 'text': 'Druhá část'}
                ],
                'text': 'První část Druhá část',
                'metrics': {'seg_count': 2},
                'asr': {'provider': 'existing', 'model': 'large-v3'},
                'processing': {'asr_settings_hash': 'abc123', 'processed_at_utc': '2024-08-22T05:43:36Z'}
            },
            {
                'call_id': '20240822_054336_71da9579',
                'recording_id': '20240822_054336_71da9579_p02',
                'duration_s': 8.3,
                'lang': 'cs',
                'segments': [
                    {'start': 0.0, 'end': 8.3, 'text': 'Třetí část'}
                ],
                'text': 'Třetí část',
                'metrics': {'seg_count': 1},
                'asr': {'provider': 'existing', 'model': 'large-v3'},
                'processing': {'asr_settings_hash': 'abc123', 'processed_at_utc': '2024-08-22T05:43:36Z'}
            }
        ]
        
        result = normalize_call_level(recording_transcripts)
        
        assert result['call_id'] == '20240822_054336_71da9579'
        assert result['duration_s'] == 18.8  # 10.5 + 8.3
        assert result['lang'] == 'cs'
        assert len(result['segments']) == 3  # 2 + 1
        assert result['segments'][0]['recording_id'] == '20240822_054336_71da9579_p01'
        assert result['segments'][2]['recording_id'] == '20240822_054336_71da9579_p02'
        assert '[--- 20240822_054336_71da9579_p01 ---]' in result['text']
        assert '[--- 20240822_054336_71da9579_p02 ---]' in result['text']
        assert result['metrics']['recording_count'] == 2
        assert result['metrics']['total_segments'] == 3
        assert result['source']['recording_ids'] == ['20240822_054336_71da9579_p01', '20240822_054336_71da9579_p02']
    
    def test_load_transcript_json(self):
        """Testuje načítání transcript JSON souboru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_path = Path(temp_dir) / "test.json"
            test_data = {
                "transcription": {"text": "Test"},
                "metadata": {"model": "large-v3"}
            }
            
            with open(transcript_path, 'w') as f:
                json.dump(test_data, f)
            
            result = load_transcript_json(transcript_path)
            assert result == test_data
    
    def test_load_transcript_json_nonexistent(self):
        """Testuje načítání neexistujícího souboru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_path = Path(temp_dir) / "nonexistent.json"
            
            with pytest.raises(ValueError, match="Transcript soubor neexistuje"):
                load_transcript_json(transcript_path)


class TestTranscribeState:
    """Testy pro TranscribeState."""
    
    def test_init_and_migration(self):
        """Testuje inicializaci a migrace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            state = TranscribeState(str(db_path))
            
            # Zkontroluj že tabulka existuje
            cursor = state.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts';")
            assert cursor.fetchone() is not None
            
            state.close()
    
    def test_upsert_transcript(self):
        """Testuje upsert transcript záznamu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            state = TranscribeState(str(db_path))
            
            # Test insert
            result = state.upsert_transcript("rec_001", "call_001", "hash123", "text456")
            assert result == 'inserted'
            
            # Test unchanged
            result = state.upsert_transcript("rec_001", "call_001", "hash123", "text456")
            assert result == 'unchanged'
            
            # Test updated (změna hash)
            result = state.upsert_transcript("rec_001", "call_001", "hash789", "text456")
            assert result == 'updated'
            
            state.close()
    
    def test_mark_ok(self):
        """Testuje označení jako úspěšný."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            state = TranscribeState(str(db_path))
            
            state.upsert_transcript("rec_001", "call_001", "hash123", "text456")
            state.mark_ok("rec_001", "2024-08-22T05:43:36Z")
            
            cursor = state.conn.execute("SELECT status FROM transcripts WHERE recording_id = ?;", ("rec_001",))
            assert cursor.fetchone()['status'] == 'ok'
            
            state.close()
    
    def test_mark_failed_transient(self):
        """Testuje označení jako selhaný (transient)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            state = TranscribeState(str(db_path))
            
            state.upsert_transcript("rec_001", "call_001", "hash123", "text456")
            retry_count = state.mark_failed_transient("rec_001", "test_error", "2024-08-22T05:43:36Z")
            
            assert retry_count == 1
            
            cursor = state.conn.execute("SELECT status, retry_count FROM transcripts WHERE recording_id = ?;", ("rec_001",))
            row = cursor.fetchone()
            assert row['status'] == 'failed-transient'
            assert row['retry_count'] == 1
            
            state.close()
    
    def test_list_todo_for_transcription(self):
        """Testuje seznam TODO pro transkripci."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            state = TranscribeState(str(db_path))
            
            # Přidej různé statusy
            state.upsert_transcript("rec_001", "call_001", "hash123", "text456")  # pending
            state.upsert_transcript("rec_002", "call_001", "hash123", "text456")  # pending
            state.upsert_transcript("rec_003", "call_001", "hash123", "text456")  # pending
            
            state.mark_ok("rec_002", "2024-08-22T05:43:36Z")  # ok
            state.mark_failed_transient("rec_003", "test_error", "2024-08-22T05:43:36Z")  # failed-transient
            
            # Test TODO
            todo = state.list_todo_for_transcription(max_retry=2)
            assert len(todo) == 2  # rec_001 (pending) + rec_003 (failed-transient, retry_count=1)
            
            # Test s limitem
            todo_limited = state.list_todo_for_transcription(max_retry=2, limit=1)
            assert len(todo_limited) == 1
            
            state.close()


class TestTranscribeRunner:
    """Testy pro TranscribeRunner."""
    
    def test_init(self):
        """Testuje inicializaci runneru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'asr': {
                    'provider': 'existing',
                    'mode': 'import',
                    'outputs_glob': '**/*.json',
                    'language': 'cs'
                },
                'io': {
                    'input_run_root': '../ingest_spinoco/output/runs',
                    'max_parallel': 2
                },
                'output': {
                    'transcripts_recordings': 'recordings.jsonl',
                    'transcripts_calls': 'calls.jsonl'
                }
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = TranscribeRunner(config_path, "test_run_001")
            
            assert runner.step_run_id == "test_run_001"
            assert runner.config['asr']['mode'] == 'import'
    
    def test_load_input_manifest(self):
        """Testuje načítání input manifestu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'asr': {'provider': 'existing', 'mode': 'import', 'outputs_glob': '**/*.json'},
                'io': {'input_run_root': str(Path(temp_dir) / 'input_runs')},
                'output': {'transcripts_recordings': 'recordings.jsonl', 'transcripts_calls': 'calls.jsonl'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup input manifest
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run'
            input_runs_dir.mkdir(parents=True)
            
            manifest_data = {
                'step_id': '01_ingest_spinoco',
                'status': 'success',
                'outputs': {'primary': 'metadata_recordings.jsonl'}
            }
            
            with open(input_runs_dir / 'manifest.json', 'w') as f:
                json.dump(manifest_data, f)
            
            runner = TranscribeRunner(config_path, "test_run_001")
            manifest = runner.load_input_manifest('test_input_run')
            
            assert manifest['step_id'] == '01_ingest_spinoco'
            assert manifest['status'] == 'success'
    
    def test_load_recordings_metadata(self):
        """Testuje načítání metadata nahrávek."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'asr': {'provider': 'existing', 'mode': 'import', 'outputs_glob': '**/*.json'},
                'io': {'input_run_root': str(Path(temp_dir) / 'input_runs')},
                'output': {'transcripts_recordings': 'recordings.jsonl', 'transcripts_calls': 'calls.jsonl'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup metadata
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run' / 'data'
            input_runs_dir.mkdir(parents=True)
            
            recordings_data = [
                {
                    'recording_id': '20240822_054336_71da9579_p01',
                    'call_id': '20240822_054336_71da9579',
                    'duration_s': 229
                },
                {
                    'recording_id': '20240822_054336_71da9579_p02',
                    'call_id': '20240822_054336_71da9579',
                    'duration_s': 180
                }
            ]
            
            with open(input_runs_dir / 'metadata_recordings.jsonl', 'w') as f:
                for recording in recordings_data:
                    json.dump(recording, f)
                    f.write('\n')
            
            runner = TranscribeRunner(config_path, "test_run_001")
            recordings = runner.load_recordings_metadata('test_input_run')
            
            assert len(recordings) == 2
            assert recordings[0]['recording_id'] == '20240822_054336_71da9579_p01'
            assert recordings[1]['recording_id'] == '20240822_054336_71da9579_p02'


class TestIntegrationScenarios:
    """Integrační testy pro různé scénáře."""
    
    def test_import_mode_happy_path(self):
        """Scénář 1: Import mode - happy path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup fixtures
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            # Vytvoř sample transcript
            sample_transcript = {
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
                    "processed_at": "2024-08-22T05:43:36Z"
                }
            }
            
            with open(fixtures_dir / "20240822_054336_71da9579_p01_transcription.json", 'w') as f:
                json.dump(sample_transcript, f)
            
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'asr': {
                    'provider': 'existing',
                    'mode': 'import',
                    'outputs_glob': '**/*_transcription.json',
                    'language': 'cs'
                },
                'io': {
                    'input_run_root': str(Path(temp_dir) / 'input_runs'),
                    'max_parallel': 2
                },
                'output': {
                    'transcripts_recordings': 'recordings.jsonl',
                    'transcripts_calls': 'calls.jsonl'
                }
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup input data
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run'
            input_runs_dir.mkdir(parents=True)
            
            # Manifest
            manifest_data = {'step_id': '01_ingest_spinoco', 'status': 'success'}
            with open(input_runs_dir / 'manifest.json', 'w') as f:
                json.dump(manifest_data, f)
            
            # Metadata
            data_dir = input_runs_dir / 'data'
            data_dir.mkdir()
            
            recordings_data = [{
                'recording_id': '20240822_054336_71da9579_p01',
                'call_id': '20240822_054336_71da9579',
                'duration_s': 5.2
            }]
            
            with open(data_dir / 'metadata_recordings.jsonl', 'w') as f:
                for recording in recordings_data:
                    json.dump(recording, f)
                    f.write('\n')
            
            # Audio (fake)
            audio_dir = data_dir / 'audio'
            audio_dir.mkdir()
            (audio_dir / '20240822_054336_71da9579_p01.ogg').touch()
            
            # Mock find_transcript_file
            with patch('run.find_transcript_file') as mock_find:
                mock_find.return_value = fixtures_dir / "20240822_054336_71da9579_p01_transcription.json"
                
                # Mock args
                class MockArgs:
                    input_run = 'test_input_run'
                    only = None
                    limit = None
                    max_retry = 2
                
                runner = TranscribeRunner(config_path, "test_run_001")
                result = runner.run(MockArgs())
                
                assert result == 0  # Success
                
                # Check outputs exist
                output_dir = runner.output_dir
                assert (output_dir / "manifest.json").exists()
                assert (output_dir / "metrics.json").exists()
                assert (output_dir / "success.ok").exists()
                assert (output_dir / "data" / "recordings.jsonl").exists()
                assert (output_dir / "data" / "calls.jsonl").exists()
                
                # Check manifest
                with open(output_dir / "manifest.json", 'r') as f:
                    manifest = json.load(f)
                
                assert manifest['status'] == 'success'
                assert manifest['counts']['transcribed'] == 1
                assert manifest['counts']['failed'] == 0
