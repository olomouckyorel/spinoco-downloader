"""
Unit testy pro common/lib/manifest.py
"""

import pytest
import tempfile
import json
from pathlib import Path
from common.lib.manifest import Manifest, create_manifest
from common.schemas.pydantic.manifest import validate_manifest_dict, validate_manifest_file


class TestManifestCreation:
    """Testy pro vytvoření manifestu."""
    
    def test_new_manifest(self):
        """Testuje vytvoření nového manifestu."""
        manifest = Manifest.new(
            schema="bh.v1.transcripts",
            schema_version="1.0.0",
            step_id="01_ingest_spinoco",
            step_run_id="01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            flow_run_id="01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            run_mode="incr"
        )
        
        data = manifest.to_dict()
        
        assert data['schema'] == "bh.v1.transcripts"
        assert data['schema_version'] == "1.0.0"
        assert data['step_id'] == "01_ingest_spinoco"
        assert data['step_run_id'] == "01J9ZC3AC9V2J9FZK2C3R8K9TQ"
        assert data['flow_run_id'] == "01J9ZC3AC9V2J9FZK2C3R8K9TQ"
        assert data['run_mode'] == "incr"
        assert data['status'] == 'running'
        assert data['started_at_utc'] is not None
        assert data['finished_at_utc'] is None
        assert data['input_refs'] == []
        assert data['outputs'] == {}
        assert data['counts'] == {}
        assert data['metrics'] == {}
        assert data['errors'] == []
        assert data['notes'] is None
        
        # Producer informace
        assert 'producer' in data
        assert 'git_sha' in data['producer']
        assert 'host' in data['producer']
        assert 'user' in data['producer']
    
    def test_create_manifest_convenience(self):
        """Testuje convenience funkci create_manifest."""
        manifest = create_manifest(
            schema="bh.v1.raw_audio",
            schema_version="1.2.0",
            step_id="02_transcribe_asr",
            run_mode="backfill"
        )
        
        data = manifest.to_dict()
        assert data['schema'] == "bh.v1.raw_audio"
        assert data['schema_version'] == "1.2.0"
        assert data['step_id'] == "02_transcribe_asr"
        assert data['run_mode'] == "backfill"
        assert data['step_run_id'] is not None  # Automaticky generované
        assert data['flow_run_id'] is None


class TestManifestBuilding:
    """Testy pro plnění manifestu."""
    
    def test_add_input_ref(self):
        """Testuje přidání input reference."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.add_input_ref("recording_id", "20240822_054336_71da9579_p01")
        manifest.add_input_ref("call_id", "20240822_054336_71da9579")
        
        data = manifest.to_dict()
        assert len(data['input_refs']) == 2
        assert data['input_refs'][0]['type'] == "recording_id"
        assert data['input_refs'][0]['value'] == "20240822_054336_71da9579_p01"
        assert data['input_refs'][1]['type'] == "call_id"
        assert data['input_refs'][1]['value'] == "20240822_054336_71da9579"
    
    def test_set_outputs(self):
        """Testuje nastavení outputs."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_outputs(
            primary="data/transcripts.jsonl",
            recording_level="data/transcripts_recordings.jsonl",
            call_level="data/transcripts_call.jsonl"
        )
        
        data = manifest.to_dict()
        assert data['outputs']['primary'] == "data/transcripts.jsonl"
        assert data['outputs']['aux']['recording_level'] == "data/transcripts_recordings.jsonl"
        assert data['outputs']['aux']['call_level'] == "data/transcripts_call.jsonl"
    
    def test_set_outputs_minimal(self):
        """Testuje nastavení pouze primary output."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_outputs(primary="data/transcripts.jsonl")
        
        data = manifest.to_dict()
        assert data['outputs']['primary'] == "data/transcripts.jsonl"
        assert data['outputs']['aux'] is None
    
    def test_set_counts(self):
        """Testuje nastavení counts."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_counts(calls=1, recordings=2, items=127, errors=0)
        
        data = manifest.to_dict()
        assert data['counts']['calls'] == 1
        assert data['counts']['recordings'] == 2
        assert data['counts']['items'] == 127
        assert data['counts']['errors'] == 0
    
    def test_merge_metrics(self):
        """Testuje přidání metrik."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.merge_metrics(avg_asr_conf=0.91, seg_count_mean=42.3)
        manifest.merge_metrics(processing_time_s=120.5)  # Přidání další metriky
        
        data = manifest.to_dict()
        assert data['metrics']['avg_asr_conf'] == 0.91
        assert data['metrics']['seg_count_mean'] == 42.3
        assert data['metrics']['processing_time_s'] == 120.5
    
    def test_add_error(self):
        """Testuje přidání error záznamu."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.add_error("20240822_054336_71da9579_p02", "corrupt_header", "OggS not found")
        manifest.add_error("20240822_054336_71da9579_p03", "network_error")
        
        data = manifest.to_dict()
        assert len(data['errors']) == 2
        assert data['errors'][0]['unit_id'] == "20240822_054336_71da9579_p02"
        assert data['errors'][0]['error_key'] == "corrupt_header"
        assert data['errors'][0]['message'] == "OggS not found"
        assert data['errors'][1]['unit_id'] == "20240822_054336_71da9579_p03"
        assert data['errors'][1]['error_key'] == "network_error"
        assert data['errors'][1]['message'] == ""
    
    def test_set_notes(self):
        """Testuje nastavení poznámek."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_notes("Test run s malým datasetem")
        
        data = manifest.to_dict()
        assert data['notes'] == "Test run s malým datasetem"


class TestManifestFinalization:
    """Testy pro finalizaci manifestu."""
    
    def test_finalize_success(self):
        """Testuje finalizaci jako úspěšnou."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_outputs(primary="data/transcripts.jsonl")
        manifest.set_counts(calls=1, recordings=2)
        
        manifest.finalize_success()
        
        data = manifest.to_dict()
        assert data['status'] == 'success'
        assert data['finished_at_utc'] is not None
        assert data['errors'] == []
    
    def test_finalize_success_with_errors_fails(self):
        """Testuje že finalizace success s errors selže."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.add_error("unit1", "error1")
        
        with pytest.raises(RuntimeError, match="Úspěšný manifest nesmí mít errors"):
            manifest.finalize_success()
    
    def test_finalize_error(self):
        """Testuje finalizaci jako selhanou."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.add_error("unit1", "error1", "Test error")
        manifest.add_error("unit2", "error2")
        
        manifest.finalize_error()
        
        data = manifest.to_dict()
        assert data['status'] == 'error'
        assert data['finished_at_utc'] is not None
        assert len(data['errors']) == 2
    
    def test_finalize_error_partial(self):
        """Testuje finalizaci jako částečně úspěšnou."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.add_error("unit1", "error1")
        
        manifest.finalize_error(partial=True)
        
        data = manifest.to_dict()
        assert data['status'] == 'partial'
        assert data['finished_at_utc'] is not None
        assert len(data['errors']) == 1
    
    def test_finalize_error_without_errors_fails(self):
        """Testuje že finalizace error bez errors selže."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        with pytest.raises(RuntimeError, match="Selhaný manifest musí mít alespoň jeden error"):
            manifest.finalize_error()
    
    def test_modify_after_finalization_fails(self):
        """Testuje že úpravy po finalizaci selžou."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.finalize_success()
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.add_input_ref("type", "value")
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.set_outputs(primary="test.jsonl")
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.set_counts(calls=1)
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.merge_metrics(test=1.0)
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.add_error("unit", "error")
        
        with pytest.raises(RuntimeError, match="Manifest je již finalizován"):
            manifest.set_notes("test")


class TestManifestPersistence:
    """Testy pro ukládání a načítání manifestu."""
    
    def test_write_and_read(self):
        """Testuje zápis a načtení manifestu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            
            # Vytvoř manifest
            manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
            manifest.set_outputs(primary="data/transcripts.jsonl")
            manifest.set_counts(calls=1, recordings=2)
            manifest.finalize_success()
            
            # Zapiš
            manifest.write(manifest_path)
            
            # Načti
            loaded_manifest = Manifest.from_path(manifest_path)
            
            # Porovnej
            assert loaded_manifest.to_dict() == manifest.to_dict()
    
    def test_write_unfinalized_fails(self):
        """Testuje že zápis nefinalizovaného manifestu selže."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            
            manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
            
            with pytest.raises(RuntimeError, match="Manifest musí být finalizován před zápisem"):
                manifest.write(manifest_path)
    
    def test_from_path_nonexistent(self):
        """Testuje načtení neexistujícího souboru."""
        with pytest.raises(ValueError, match="Manifest soubor neexistuje"):
            Manifest.from_path("nonexistent.json")
    
    def test_from_path_invalid_json(self):
        """Testuje načtení neplatného JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "invalid.json"
            
            with open(manifest_path, 'w') as f:
                f.write("invalid json content")
            
            with pytest.raises(ValueError, match="Manifest soubor není platný JSON"):
                Manifest.from_path(manifest_path)


class TestManifestValidation:
    """Testy pro validaci manifestu."""
    
    def test_validate_success(self):
        """Testuje validaci úspěšného manifestu."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        manifest.set_outputs(primary="data/transcripts.jsonl")
        manifest.set_counts(calls=1, recordings=2)
        manifest.finalize_success()
        
        # Validace by neměla selhat
        manifest.validate()
    
    def test_validate_error(self):
        """Testuje validaci selhaného manifestu."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        manifest.set_outputs(primary="data/transcripts.jsonl")
        manifest.add_error("unit1", "error1")
        manifest.finalize_error()
        
        # Validace by neměla selhat
        manifest.validate()
    
    def test_validate_missing_primary_output(self):
        """Testuje validaci manifestu bez primary output."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        manifest.set_outputs(primary="")  # Prázdný primary
        manifest.finalize_success()
        
        with pytest.raises(ValueError, match="outputs.primary je povinné"):
            manifest.validate()


class TestPydanticValidation:
    """Testy pro Pydantic validaci."""
    
    def test_validate_manifest_dict_success(self):
        """Testuje validaci úspěšného manifest dict."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.0.0",
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "flow_run_id": None,
            "producer": {
                "git_sha": "abc123",
                "host": "test-host",
                "user": "test-user"
            },
            "run_mode": "incr",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "finished_at_utc": "2024-08-22T05:44:00Z",
            "status": "success",
            "input_refs": [],
            "outputs": {
                "primary": "data/transcripts.jsonl"
            },
            "counts": {"calls": 1, "recordings": 2},
            "metrics": {"avg_asr_conf": 0.91},
            "errors": [],
            "notes": None
        }
        
        model = validate_manifest_dict(data)
        assert model.schema_id == "bh.v1.transcripts"
        assert model.status == "success"
    
    def test_validate_manifest_dict_invalid_schema_version(self):
        """Testuje validaci s neplatným schema_version."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.2",  # Neplatné semver
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "producer": {"git_sha": "abc123", "host": "test", "user": "test"},
            "run_mode": "incr",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "status": "success",
            "outputs": {"primary": "data/transcripts.jsonl"}
        }
        
        with pytest.raises(ValueError, match="schema_version musí být ve formátu semver"):
            validate_manifest_dict(data)
    
    def test_validate_manifest_dict_invalid_status(self):
        """Testuje validaci s neplatným status."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.0.0",
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "producer": {"git_sha": "abc123", "host": "test", "user": "test"},
            "run_mode": "incr",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "status": "invalid_status",
            "outputs": {"primary": "data/transcripts.jsonl"}
        }
        
        with pytest.raises(ValueError, match="status musí být jeden z"):
            validate_manifest_dict(data)
    
    def test_validate_manifest_dict_invalid_run_mode(self):
        """Testuje validaci s neplatným run_mode."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.0.0",
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "producer": {"git_sha": "abc123", "host": "test", "user": "test"},
            "run_mode": "invalid_mode",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "status": "success",
            "outputs": {"primary": "data/transcripts.jsonl"}
        }
        
        with pytest.raises(ValueError, match="run_mode musí být jeden z"):
            validate_manifest_dict(data)
    
    def test_validate_manifest_dict_success_with_errors_fails(self):
        """Testuje validaci success status s errors."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.0.0",
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "producer": {"git_sha": "abc123", "host": "test", "user": "test"},
            "run_mode": "incr",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "status": "success",
            "outputs": {"primary": "data/transcripts.jsonl"},
            "errors": [{"unit_id": "unit1", "error_key": "error1", "message": "test"}]
        }
        
        with pytest.raises(ValueError, match="status='success' nesmí mít errors"):
            validate_manifest_dict(data)
    
    def test_validate_manifest_dict_error_without_errors_fails(self):
        """Testuje validaci error status bez errors."""
        data = {
            "schema": "bh.v1.transcripts",
            "schema_version": "1.0.0",
            "step_id": "01_ingest_spinoco",
            "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
            "producer": {"git_sha": "abc123", "host": "test", "user": "test"},
            "run_mode": "incr",
            "started_at_utc": "2024-08-22T05:43:36Z",
            "status": "error",
            "outputs": {"primary": "data/transcripts.jsonl"},
            "errors": []
        }
        
        with pytest.raises(ValueError, match="status='error' musí mít alespoň jeden error"):
            validate_manifest_dict(data)


class TestManifestIdempotence:
    """Testy pro idempotenci manifestu."""
    
    def test_to_dict_stable_order(self):
        """Testuje že to_dict() má stabilní pořadí klíčů."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        manifest.set_outputs(primary="data/transcripts.jsonl")
        manifest.set_counts(calls=1, recordings=2)
        manifest.finalize_success()
        
        # Získej dict vícekrát
        dict1 = manifest.to_dict()
        dict2 = manifest.to_dict()
        
        # Pořadí klíčů musí být stejné
        assert list(dict1.keys()) == list(dict2.keys())
        
        # Round-trip test
        json_str1 = json.dumps(dict1, sort_keys=True)
        json_str2 = json.dumps(dict2, sort_keys=True)
        assert json_str1 == json_str2


class TestIntegration:
    """Integrační testy."""
    
    def test_full_workflow(self):
        """Testuje kompletní workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            
            # 1. Vytvoř manifest
            manifest = create_manifest(
                schema="bh.v1.transcripts",
                schema_version="1.0.0",
                step_id="01_ingest_spinoco",
                run_mode="incr"
            )
            
            # 2. Přidej input refs
            manifest.add_input_ref("recording_id", "20240822_054336_71da9579_p01")
            manifest.add_input_ref("recording_id", "20240822_054336_71da9579_p02")
            
            # 3. Nastav outputs
            manifest.set_outputs(
                primary="data/transcripts.jsonl",
                recording_level="data/transcripts_recordings.jsonl",
                call_level="data/transcripts_call.jsonl"
            )
            
            # 4. Nastav counts
            manifest.set_counts(calls=1, recordings=2, items=127, errors=0)
            
            # 5. Přidej metriky
            manifest.merge_metrics(avg_asr_conf=0.91, seg_count_mean=42.3)
            
            # 6. Přidej poznámky
            manifest.set_notes("Test run s malým datasetem")
            
            # 7. Finalizuj jako úspěšný
            manifest.finalize_success()
            
            # 8. Validuj
            manifest.validate()
            
            # 9. Zapiš
            manifest.write(manifest_path)
            
            # 10. Načti a validuj
            loaded_manifest = Manifest.from_path(manifest_path)
            loaded_manifest.validate()
            
            # 11. Porovnej
            assert loaded_manifest.to_dict() == manifest.to_dict()
    
    def test_error_workflow(self):
        """Testuje workflow s chybami."""
        manifest = create_manifest("bh.v1.transcripts", "1.0.0", "01_ingest_spinoco")
        
        manifest.set_outputs(primary="data/transcripts.jsonl")
        manifest.set_counts(calls=1, recordings=2, errors=1)
        
        # Přidej chyby
        manifest.add_error("20240822_054336_71da9579_p02", "corrupt_header", "OggS not found")
        
        # Finalizuj jako částečně úspěšný
        manifest.finalize_error(partial=True)
        
        # Validuj
        manifest.validate()
        
        data = manifest.to_dict()
        assert data['status'] == 'partial'
        assert len(data['errors']) == 1
        assert data['counts']['errors'] == 1
