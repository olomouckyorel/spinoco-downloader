"""
Integrační testy pro steps/01_ingest_spinoco.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import sys

# Přidej common library do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.lib import State, Manifest
from client import FakeSpinocoClient
from run import IngestRunner


class TestIngestRunner:
    """Testy pro IngestRunner."""
    
    def test_init_with_fake_client(self):
        """Testuje inicializaci s fake clientem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = IngestRunner(config_path, "test_run_001")
            
            assert runner.step_run_id == "test_run_001"
            assert isinstance(runner.client, FakeSpinocoClient)
            assert runner.config['test_mode'] is True
    
    def test_fetch_calls(self):
        """Testuje načítání hovorů."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup
            config_path = Path(temp_dir) / "config.yaml"
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            # Vytvoř test fixtures
            call_data = {
                "id": "test_call_001",
                "lastUpdate": 1724305416000,
                "tpe": {"name": "Test"},
                "owner": {"id": "user1", "name": "Test User"}
            }
            
            with open(fixtures_dir / "call_task.json", 'w') as f:
                json.dump(call_data, f)
            
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = IngestRunner(config_path, "test_run_001")
            runner.client = FakeSpinocoClient(fixtures_dir)
            
            # Test
            calls = runner.fetch_calls(limit=1)
            
            assert len(calls) == 1
            assert calls[0]['call_task']['id'] == "test_call_001"
            assert 'normalized_call' in calls[0]
            assert calls[0]['normalized_call']['call_id'] is not None
    
    def test_fetch_recordings(self):
        """Testuje načítání nahrávek."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup
            config_path = Path(temp_dir) / "config.yaml"
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            # Vytvoř test fixtures
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
            
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = IngestRunner(config_path, "test_run_001")
            runner.client = FakeSpinocoClient(fixtures_dir)
            
            # Test
            calls = runner.fetch_calls(limit=1)
            recordings = runner.fetch_recordings(calls)
            
            assert len(recordings) == 1
            assert recordings[0]['spinoco_recording_id'] == "test_call_001_rec_01"
            assert recordings[0]['recording_id'] is not None
    
    def test_validate_ogg_file(self):
        """Testuje validaci OGG souborů."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = IngestRunner(config_path, "test_run_001")
            
            # Test platný OGG soubor
            valid_ogg = Path(temp_dir) / "valid.ogg"
            with open(valid_ogg, 'wb') as f:
                f.write(b'OggS' + b'\x00' * 23)
            
            assert runner._validate_ogg_file(valid_ogg) is True
            
            # Test neplatný soubor
            invalid_file = Path(temp_dir) / "invalid.ogg"
            with open(invalid_file, 'wb') as f:
                f.write(b'INVALID')
            
            assert runner._validate_ogg_file(invalid_file) is False


class TestIntegrationScenarios:
    """Integrační testy pro různé scénáře."""
    
    def test_happy_path_scenario(self):
        """Scénář 1: Happy path - vše funguje."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup fixtures
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            call_data = {
                "id": "happy_call_001",
                "lastUpdate": 1724305416000,
                "tpe": {"name": "Happy Test"},
                "owner": {"id": "user1", "name": "Happy User"}
            }
            
            recordings_data = [
                {
                    "id": "happy_rec_001",
                    "date": 1724305416000,
                    "duration": 229,
                    "vm": False,
                    "available": True,
                    "transcriptions": {}
                },
                {
                    "id": "happy_rec_002",
                    "date": 1724305417000,
                    "duration": 180,
                    "vm": False,
                    "available": True,
                    "transcriptions": {}
                }
            ]
            
            with open(fixtures_dir / "call_task.json", 'w') as f:
                json.dump(call_data, f)
            
            with open(fixtures_dir / "recordings.json", 'w') as f:
                json.dump(recordings_data, f)
            
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Run ingest
            runner = IngestRunner(config_path, "happy_test_001")
            runner.client = FakeSpinocoClient(fixtures_dir)
            
            # Mock args
            class MockArgs:
                since = None
                limit = 1
                only = None
                max_retry = 3
            
            result = runner.run(MockArgs())
            
            # Verify results
            assert result == 0  # Success
            
            # Check outputs exist
            output_dir = runner.output_dir
            assert (output_dir / "manifest.json").exists()
            assert (output_dir / "metrics.json").exists()
            assert (output_dir / "success.ok").exists()
            assert (output_dir / "data" / "calls.jsonl").exists()
            assert (output_dir / "data" / "recordings.jsonl").exists()
            
            # Check manifest
            with open(output_dir / "manifest.json", 'r') as f:
                manifest = json.load(f)
            
            assert manifest['status'] == 'success'
            assert manifest['counts']['downloaded'] == 2
            assert manifest['counts']['failed'] == 0
            
            # Check audio files
            audio_dir = output_dir / "data" / "audio"
            assert len(list(audio_dir.glob("*.ogg"))) == 2
    
    def test_partial_fail_scenario(self):
        """Scénář 2: Partial fail - jedna nahrávka selže."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup fixtures s jednou "fail" nahrávkou
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            call_data = {
                "id": "partial_call_001",
                "lastUpdate": 1724305416000,
                "tpe": {"name": "Partial Test"},
                "owner": {"id": "user1", "name": "Partial User"}
            }
            
            recordings_data = [
                {
                    "id": "partial_rec_001",
                    "date": 1724305416000,
                    "duration": 229,
                    "vm": False,
                    "available": True,
                    "transcriptions": {}
                },
                {
                    "id": "fail_rec_002",  # Toto selže kvůli "fail" v názvu
                    "date": 1724305417000,
                    "duration": 180,
                    "vm": False,
                    "available": True,
                    "transcriptions": {}
                }
            ]
            
            with open(fixtures_dir / "call_task.json", 'w') as f:
                json.dump(call_data, f)
            
            with open(fixtures_dir / "recordings.json", 'w') as f:
                json.dump(recordings_data, f)
            
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Run ingest
            runner = IngestRunner(config_path, "partial_test_001")
            runner.client = FakeSpinocoClient(fixtures_dir)
            
            # Mock args
            class MockArgs:
                since = None
                limit = 1
                only = None
                max_retry = 3
            
            result = runner.run(MockArgs())
            
            # Verify results
            assert result == 1  # Partial success
            
            # Check outputs exist
            output_dir = runner.output_dir
            assert (output_dir / "manifest.json").exists()
            assert (output_dir / "error.json").exists()
            assert not (output_dir / "success.ok").exists()
            
            # Check manifest
            with open(output_dir / "manifest.json", 'r') as f:
                manifest = json.load(f)
            
            assert manifest['status'] == 'partial'
            assert manifest['counts']['downloaded'] == 1
            assert manifest['counts']['failed'] == 1
            
            # Check error.json
            with open(output_dir / "error.json", 'r') as f:
                error_data = json.load(f)
            
            assert 'failed_ids' in error_data
            assert len(error_data['failed_ids']) == 1
    
    def test_retry_scenario(self):
        """Scénář 3: Retry - oprava selhané nahrávky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup fixtures
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            call_data = {
                "id": "retry_call_001",
                "lastUpdate": 1724305416000,
                "tpe": {"name": "Retry Test"},
                "owner": {"id": "user1", "name": "Retry User"}
            }
            
            recordings_data = [
                {
                    "id": "retry_rec_001",
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
            
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'test_mode': True,
                'auth': {'api_base_url': 'https://test.com', 'token': 'test'},
                'fetch': {'page_size': 100},
                'download': {'concurrency': 2, 'validate_ogg_header': True, 'temp_suffix': '.partial'},
                'output': {'metadata_calls': 'calls.jsonl', 'metadata_recordings': 'recordings.jsonl', 'audio_dir': 'audio/'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Run ingest s --only pro retry
            runner = IngestRunner(config_path, "retry_test_001")
            runner.client = FakeSpinocoClient(fixtures_dir)
            
            # Mock args pro retry
            class MockArgs:
                since = None
                limit = 1
                only = "retry_call_001_rec_01"  # Retry konkrétní nahrávky
                max_retry = 3
            
            result = runner.run(MockArgs())
            
            # Verify results
            assert result == 0  # Success po retry
            
            # Check manifest
            output_dir = runner.output_dir
            with open(output_dir / "manifest.json", 'r') as f:
                manifest = json.load(f)
            
            assert manifest['status'] == 'success'
            assert manifest['counts']['downloaded'] == 1
            assert manifest['counts']['failed'] == 0


class TestFakeSpinocoClient:
    """Testy pro FakeSpinocoClient."""
    
    def test_list_calls(self):
        """Testuje list_calls."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
            call_data = {
                "id": "test_call_001",
                "lastUpdate": 1724305416000,
                "tpe": {"name": "Test"},
                "owner": {"id": "user1", "name": "Test User"}
            }
            
            with open(fixtures_dir / "call_task.json", 'w') as f:
                json.dump(call_data, f)
            
            client = FakeSpinocoClient(fixtures_dir)
            calls = list(client.list_calls(limit=2))
            
            assert len(calls) == 2
            assert calls[0]['id'] == "test_call_001_00"
            assert calls[1]['id'] == "test_call_001_01"
    
    def test_list_recordings(self):
        """Testuje list_recordings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_dir = Path(temp_dir) / "fixtures"
            fixtures_dir.mkdir()
            
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
            
            with open(fixtures_dir / "recordings.json", 'w') as f:
                json.dump(recordings_data, f)
            
            client = FakeSpinocoClient(fixtures_dir)
            recordings = client.list_recordings("test_call_001")
            
            assert len(recordings) == 1
            assert recordings[0]['id'] == "test_call_001_rec_01"
    
    def test_download_recording_success(self):
        """Testuje úspěšné stahování nahrávky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_dir = Path(temp_dir) / "fixtures"
            client = FakeSpinocoClient(fixtures_dir)
            
            output_path = Path(temp_dir) / "test.ogg"
            size = client.download_recording("success_rec_001", output_path)
            
            assert output_path.exists()
            assert size > 0
            
            # Zkontroluj že je to platný OGG
            with open(output_path, 'rb') as f:
                header = f.read(4)
                assert header == b'OggS'
    
    def test_download_recording_fail(self):
        """Testuje selhané stahování nahrávky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_dir = Path(temp_dir) / "fixtures"
            client = FakeSpinocoClient(fixtures_dir)
            
            output_path = Path(temp_dir) / "test.ogg"
            size = client.download_recording("fail_rec_001", output_path)
            
            assert output_path.exists()
            assert size == 15  # Velikost poškozeného souboru
            
            # Zkontroluj že není platný OGG
            with open(output_path, 'rb') as f:
                header = f.read(4)
                assert header != b'OggS'
