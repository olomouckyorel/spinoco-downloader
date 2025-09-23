"""
Integrační testy pro steps/03_anonymize.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Přidej common library do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.lib import Manifest
from anonymizer import (
    PIIAnonymizer, redact_recording, redact_call, 
    load_transcript_file, save_transcript_file, save_vault_map,
    get_call_recordings, aggregate_pii_stats
)
from run import AnonymizeRunner


class TestPIIAnonymizer:
    """Testy pro PIIAnonymizer."""
    
    def test_init(self):
        """Testuje inicializaci anonymizeru."""
        config = {
            'tags_prefix': '@',
            'redact_phone': True,
            'redact_email': True,
            'redact_iban': True,
            'redact_address': False
        }
        
        anonymizer = PIIAnonymizer(config)
        
        assert anonymizer.tags_prefix == '@'
        assert 'PHONE' in anonymizer.patterns
        assert 'EMAIL' in anonymizer.patterns
        assert 'IBAN' in anonymizer.patterns
        assert 'ADDRESS' not in anonymizer.patterns
    
    def test_redact_text_phone(self):
        """Testuje redigování telefonních čísel."""
        config = {'tags_prefix': '@', 'redact_phone': True}
        anonymizer = PIIAnonymizer(config)
        
        text = "Zavolejte na +420 123 456 789 nebo 777 888 999"
        context = {}
        
        redacted, counts = anonymizer.redact_text(text, context)
        
        assert '@PHONE_1' in redacted
        assert '@PHONE_2' in redacted
        assert '+420 123 456 789' not in redacted
        assert '777 888 999' not in redacted
        assert counts['PHONE'] == 2
        assert context['PHONE']['@PHONE_1'] == '+420 123 456 789'
        assert context['PHONE']['@PHONE_2'] == '777 888 999'
    
    def test_redact_text_email(self):
        """Testuje redigování email adres."""
        config = {'tags_prefix': '@', 'redact_email': True}
        anonymizer = PIIAnonymizer(config)
        
        text = "Napište na jan.novak@example.com nebo info@firma.cz"
        context = {}
        
        redacted, counts = anonymizer.redact_text(text, context)
        
        assert '@EMAIL_1' in redacted
        assert '@EMAIL_2' in redacted
        assert 'jan.novak@example.com' not in redacted
        assert 'info@firma.cz' not in redacted
        assert counts['EMAIL'] == 2
    
    def test_redact_text_iban(self):
        """Testuje redigování IBAN."""
        config = {'tags_prefix': '@', 'redact_iban': True}
        anonymizer = PIIAnonymizer(config)
        
        text = "IBAN je CZ65 0800 0000 1920 0014 5399"
        context = {}
        
        redacted, counts = anonymizer.redact_text(text, context)
        
        assert '@IBAN_1' in redacted
        assert 'CZ65 0800 0000 1920 0014 5399' not in redacted
        assert counts['IBAN'] == 1
    
    def test_redact_text_deterministic(self):
        """Testuje deterministické tagování."""
        config = {'tags_prefix': '@', 'redact_phone': True}
        anonymizer = PIIAnonymizer(config)
        
        text1 = "Telefon +420 123 456 789"
        text2 = "Další telefon +420 123 456 789"
        
        context = {}
        
        redacted1, _ = anonymizer.redact_text(text1, context)
        redacted2, _ = anonymizer.redact_text(text2, context)
        
        # Stejné číslo by mělo dostat stejný tag
        assert '@PHONE_1' in redacted1
        assert '@PHONE_1' in redacted2
        assert '@PHONE_2' not in redacted2
    
    def test_create_vault_map(self):
        """Testuje vytvoření vault map."""
        config = {'tags_prefix': '@'}
        anonymizer = PIIAnonymizer(config)
        
        context = {
            'PHONE': {
                '@PHONE_1': '+420 123 456 789',
                '@PHONE_2': '777 888 999'
            },
            'EMAIL': {
                '@EMAIL_1': 'jan.novak@example.com'
            }
        }
        
        vault_map = anonymizer.create_vault_map(context, salt="test_salt")
        
        assert '@PHONE_1' in vault_map
        assert '@PHONE_2' in vault_map
        assert '@EMAIL_1' in vault_map
        
        # Zkontroluj že hash je deterministický
        assert len(vault_map['@PHONE_1']) == 64  # SHA256 hex length
        assert vault_map['@PHONE_1'] != vault_map['@PHONE_2']


class TestAnonymizerFunctions:
    """Testy pro anonymizer funkce."""
    
    def test_redact_recording(self):
        """Testuje redigování recording-level transkriptu."""
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
        
        config = {'tags_prefix': '@', 'redact_phone': True}
        context = {}
        
        redacted = redact_recording(recording, config, context)
        
        assert redacted['call_id'] == recording['call_id']
        assert redacted['recording_id'] == recording['recording_id']
        assert '@PHONE_1' in redacted['text']
        assert '@PHONE_1' in redacted['segments'][0]['text']
        assert 'pii_stats' in redacted
        assert redacted['pii_stats']['total_replacements'] == 1
        assert redacted['pii_stats']['by_type']['PHONE'] == 1
    
    def test_redact_call(self):
        """Testuje redigování call-level transkriptu."""
        call = {
            'call_id': '20240822_054336_71da9579',
            'text': 'Zavolejte na +420 123 456 789 nebo napište na info@firma.cz',
            'segments': [
                {
                    'start': 0.0,
                    'end': 5.0,
                    'text': 'Zavolejte na +420 123 456 789',
                    'recording_id': '20240822_054336_71da9579_p01'
                },
                {
                    'start': 5.0,
                    'end': 10.0,
                    'text': 'nebo napište na info@firma.cz',
                    'recording_id': '20240822_054336_71da9579_p01'
                }
            ]
        }
        
        config = {'tags_prefix': '@', 'redact_phone': True, 'redact_email': True}
        
        redacted_call, vault_map = redact_call(call, config)
        
        assert redacted_call['call_id'] == call['call_id']
        assert '@PHONE_1' in redacted_call['text']
        assert '@EMAIL_1' in redacted_call['text']
        assert '@PHONE_1' in redacted_call['segments'][0]['text']
        assert '@EMAIL_1' in redacted_call['segments'][1]['text']
        assert 'pii_stats' in redacted_call
        assert redacted_call['pii_stats']['total_replacements'] == 2
        
        # Vault map
        assert '@PHONE_1' in vault_map
        assert '@EMAIL_1' in vault_map
    
    def test_load_transcript_file(self):
        """Testuje načítání transcript JSONL souboru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_path = Path(temp_dir) / "test.jsonl"
            
            test_data = [
                {'call_id': 'call_001', 'text': 'Test 1'},
                {'call_id': 'call_002', 'text': 'Test 2'}
            ]
            
            with open(transcript_path, 'w') as f:
                for item in test_data:
                    json.dump(item, f)
                    f.write('\n')
            
            result = load_transcript_file(transcript_path)
            assert len(result) == 2
            assert result[0]['call_id'] == 'call_001'
            assert result[1]['call_id'] == 'call_002'
    
    def test_save_transcript_file(self):
        """Testuje ukládání transcript JSONL souboru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_path = Path(temp_dir) / "test.jsonl"
            
            test_data = [
                {'call_id': 'call_001', 'text': 'Test 1'},
                {'call_id': 'call_002', 'text': 'Test 2'}
            ]
            
            save_transcript_file(test_data, transcript_path)
            
            assert transcript_path.exists()
            
            with open(transcript_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 2
                assert json.loads(lines[0])['call_id'] == 'call_001'
    
    def test_save_vault_map(self):
        """Testuje ukládání vault map."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_map_path = Path(temp_dir) / "vault.json"
            
            vault_map = {
                '@PHONE_1': 'hash1',
                '@EMAIL_1': 'hash2'
            }
            
            save_vault_map(vault_map, vault_map_path)
            
            assert vault_map_path.exists()
            
            with open(vault_map_path, 'r') as f:
                loaded = json.load(f)
                assert loaded == vault_map
    
    def test_get_call_recordings(self):
        """Testuje získání recordingů pro call."""
        recordings = [
            {'call_id': 'call_001', 'recording_id': 'rec_001_p01'},
            {'call_id': 'call_001', 'recording_id': 'rec_001_p02'},
            {'call_id': 'call_002', 'recording_id': 'rec_002_p01'}
        ]
        
        call_recordings = get_call_recordings(recordings, 'call_001')
        
        assert len(call_recordings) == 2
        assert call_recordings[0]['recording_id'] == 'rec_001_p01'
        assert call_recordings[1]['recording_id'] == 'rec_001_p02'
    
    def test_aggregate_pii_stats(self):
        """Testuje agregaci PII statistik."""
        recordings = [
            {
                'pii_stats': {
                    'total_replacements': 2,
                    'by_type': {'PHONE': 1, 'EMAIL': 1}
                }
            },
            {
                'pii_stats': {
                    'total_replacements': 1,
                    'by_type': {'PHONE': 1}
                }
            }
        ]
        
        stats = aggregate_pii_stats(recordings)
        
        assert stats['total_replacements'] == 3
        assert stats['by_type']['PHONE'] == 2
        assert stats['by_type']['EMAIL'] == 1
        assert stats['recording_count'] == 2


class TestAnonymizeRunner:
    """Testy pro AnonymizeRunner."""
    
    def test_init(self):
        """Testuje inicializaci runneru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'anonymize': {
                    'tags_prefix': '@',
                    'redact_phone': True,
                    'redact_email': True,
                    'make_vault_map': True
                },
                'io': {
                    'input_run_root': '../transcribe_asr_adapter/output/runs',
                    'max_parallel': 2
                },
                'output': {
                    'transcripts_recordings_redacted': 'recordings.jsonl',
                    'transcripts_calls_redacted': 'calls.jsonl',
                    'vault_map_dir': 'vault_map'
                }
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            runner = AnonymizeRunner(config_path, "test_run_001")
            
            assert runner.step_run_id == "test_run_001"
            assert runner.config['anonymize']['redact_phone'] is True
    
    def test_load_input_manifest(self):
        """Testuje načítání input manifestu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'anonymize': {'tags_prefix': '@', 'redact_phone': True},
                'io': {'input_run_root': str(Path(temp_dir) / 'input_runs')},
                'output': {'transcripts_recordings_redacted': 'recordings.jsonl', 'transcripts_calls_redacted': 'calls.jsonl', 'vault_map_dir': 'vault_map'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup input manifest
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run'
            input_runs_dir.mkdir(parents=True)
            
            manifest_data = {
                'step_id': '02_transcribe_asr_adapter',
                'status': 'success',
                'outputs': {'primary': 'transcripts_recordings.jsonl'}
            }
            
            with open(input_runs_dir / 'manifest.json', 'w') as f:
                json.dump(manifest_data, f)
            
            runner = AnonymizeRunner(config_path, "test_run_001")
            manifest = runner.load_input_manifest('test_input_run')
            
            assert manifest['step_id'] == '02_transcribe_asr_adapter'
            assert manifest['status'] == 'success'
    
    def test_load_transcripts(self):
        """Testuje načítání transkriptů."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'anonymize': {'tags_prefix': '@', 'redact_phone': True},
                'io': {'input_run_root': str(Path(temp_dir) / 'input_runs')},
                'output': {'transcripts_recordings_redacted': 'recordings.jsonl', 'transcripts_calls_redacted': 'calls.jsonl', 'vault_map_dir': 'vault_map'}
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup transcripts
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run' / 'data'
            input_runs_dir.mkdir(parents=True)
            
            recordings_data = [
                {'call_id': 'call_001', 'recording_id': 'rec_001_p01', 'text': 'Test 1'},
                {'call_id': 'call_001', 'recording_id': 'rec_001_p02', 'text': 'Test 2'}
            ]
            
            calls_data = [
                {'call_id': 'call_001', 'text': 'Test call 1'}
            ]
            
            with open(input_runs_dir / 'transcripts_recordings.jsonl', 'w') as f:
                for recording in recordings_data:
                    json.dump(recording, f)
                    f.write('\n')
            
            with open(input_runs_dir / 'transcripts_calls.jsonl', 'w') as f:
                for call in calls_data:
                    json.dump(call, f)
                    f.write('\n')
            
            runner = AnonymizeRunner(config_path, "test_run_001")
            recordings, calls = runner.load_transcripts('test_input_run')
            
            assert len(recordings) == 2
            assert len(calls) == 1
            assert recordings[0]['call_id'] == 'call_001'
            assert calls[0]['call_id'] == 'call_001'


class TestIntegrationScenarios:
    """Integrační testy pro různé scénáře."""
    
    def test_happy_path_workflow(self):
        """Scénář 1: Happy path - redigování hovorů s PII."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'anonymize': {
                    'tags_prefix': '@',
                    'redact_phone': True,
                    'redact_email': True,
                    'redact_iban': True,
                    'make_vault_map': True
                },
                'io': {
                    'input_run_root': str(Path(temp_dir) / 'input_runs'),
                    'max_parallel': 2
                },
                'output': {
                    'transcripts_recordings_redacted': 'recordings.jsonl',
                    'transcripts_calls_redacted': 'calls.jsonl',
                    'vault_map_dir': 'vault_map'
                }
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup input data
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run'
            input_runs_dir.mkdir(parents=True)
            
            # Manifest
            manifest_data = {'step_id': '02_transcribe_asr_adapter', 'status': 'success'}
            with open(input_runs_dir / 'manifest.json', 'w') as f:
                json.dump(manifest_data, f)
            
            # Data
            data_dir = input_runs_dir / 'data'
            data_dir.mkdir()
            
            recordings_data = [
                {
                    'call_id': '20240822_054336_71da9579',
                    'recording_id': '20240822_054336_71da9579_p01',
                    'text': 'Zavolejte na +420 123 456 789 nebo napište na info@firma.cz'
                }
            ]
            
            calls_data = [
                {
                    'call_id': '20240822_054336_71da9579',
                    'text': 'Zavolejte na +420 123 456 789 nebo napište na info@firma.cz'
                }
            ]
            
            with open(data_dir / 'transcripts_recordings.jsonl', 'w') as f:
                for recording in recordings_data:
                    json.dump(recording, f)
                    f.write('\n')
            
            with open(data_dir / 'transcripts_calls.jsonl', 'w') as f:
                for call in calls_data:
                    json.dump(call, f)
                    f.write('\n')
            
            # Mock args
            class MockArgs:
                input_run = 'test_input_run'
                only = None
                limit = None
                max_retry = 2
            
            runner = AnonymizeRunner(config_path, "test_run_001")
            result = runner.run(MockArgs())
            
            assert result == 0  # Success
            
            # Check outputs exist
            output_dir = runner.output_dir
            assert (output_dir / "manifest.json").exists()
            assert (output_dir / "metrics.json").exists()
            assert (output_dir / "success.ok").exists()
            assert (output_dir / "data" / "recordings.jsonl").exists()
            assert (output_dir / "data" / "calls.jsonl").exists()
            assert (output_dir / "data" / "vault_map" / "20240822_054336_71da9579.json").exists()
            
            # Check manifest
            with open(output_dir / "manifest.json", 'r') as f:
                manifest = json.load(f)
            
            assert manifest['status'] == 'success'
            assert manifest['counts']['redacted'] == 1
            assert manifest['counts']['failed'] == 0
            
            # Check redacted content
            with open(output_dir / "data" / "recordings.jsonl", 'r') as f:
                redacted_recordings = [json.loads(line) for line in f if line.strip()]
            
            assert len(redacted_recordings) == 1
            assert '@PHONE_1' in redacted_recordings[0]['text']
            assert '@EMAIL_1' in redacted_recordings[0]['text']
            assert '+420 123 456 789' not in redacted_recordings[0]['text']
            assert 'info@firma.cz' not in redacted_recordings[0]['text']
    
    def test_idempotence(self):
        """Scénář 2: Idempotence - stejné vstupy → identické výsledky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup config
            config_path = Path(temp_dir) / "config.yaml"
            config = {
                'anonymize': {
                    'tags_prefix': '@',
                    'redact_phone': True,
                    'redact_email': True,
                    'make_vault_map': True
                },
                'io': {
                    'input_run_root': str(Path(temp_dir) / 'input_runs'),
                    'max_parallel': 2
                },
                'output': {
                    'transcripts_recordings_redacted': 'recordings.jsonl',
                    'transcripts_calls_redacted': 'calls.jsonl',
                    'vault_map_dir': 'vault_map'
                }
            }
            
            with open(config_path, 'w') as f:
                import yaml
                yaml.dump(config, f)
            
            # Setup input data
            input_runs_dir = Path(temp_dir) / 'input_runs' / 'test_input_run'
            input_runs_dir.mkdir(parents=True)
            
            # Manifest
            manifest_data = {'step_id': '02_transcribe_asr_adapter', 'status': 'success'}
            with open(input_runs_dir / 'manifest.json', 'w') as f:
                json.dump(manifest_data, f)
            
            # Data
            data_dir = input_runs_dir / 'data'
            data_dir.mkdir()
            
            test_text = "Zavolejte na +420 123 456 789 nebo napište na info@firma.cz"
            
            recordings_data = [
                {
                    'call_id': '20240822_054336_71da9579',
                    'recording_id': '20240822_054336_71da9579_p01',
                    'text': test_text
                }
            ]
            
            calls_data = [
                {
                    'call_id': '20240822_054336_71da9579',
                    'text': test_text
                }
            ]
            
            with open(data_dir / 'transcripts_recordings.jsonl', 'w') as f:
                for recording in recordings_data:
                    json.dump(recording, f)
                    f.write('\n')
            
            with open(data_dir / 'transcripts_calls.jsonl', 'w') as f:
                for call in calls_data:
                    json.dump(call, f)
                    f.write('\n')
            
            # Mock args
            class MockArgs:
                input_run = 'test_input_run'
                only = None
                limit = None
                max_retry = 2
            
            # První běh
            runner1 = AnonymizeRunner(config_path, "test_run_001")
            result1 = runner1.run(MockArgs())
            
            # Druhý běh
            runner2 = AnonymizeRunner(config_path, "test_run_002")
            result2 = runner2.run(MockArgs())
            
            assert result1 == 0
            assert result2 == 0
            
            # Zkontroluj že výsledky jsou identické
            with open(runner1.output_dir / "data" / "recordings.jsonl", 'r') as f:
                content1 = f.read()
            
            with open(runner2.output_dir / "data" / "recordings.jsonl", 'r') as f:
                content2 = f.read()
            
            # Obsah by měl být identický (kromě případných timestampů)
            lines1 = content1.strip().split('\n')
            lines2 = content2.strip().split('\n')
            
            assert len(lines1) == len(lines2)
            
            for line1, line2 in zip(lines1, lines2):
                data1 = json.loads(line1)
                data2 = json.loads(line2)
                
                # Zkontroluj že PII tagy jsou stejné
                assert data1['text'] == data2['text']
                assert data1['pii_stats'] == data2['pii_stats']
