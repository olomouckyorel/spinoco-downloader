"""
Unit testy pro common/lib/metadata.py
"""

import pytest
from datetime import datetime, timezone
from common.lib.metadata import (
    utc_iso_from_ms, normalize_call_task, build_recordings_metadata,
    spinoco_to_internal, validate_call_task, validate_recording
)


class TestUTCISO:
    """Testy pro utc_iso_from_ms."""
    
    def test_utc_iso_from_ms_happy_path(self):
        """Testuje základní funkcionalitu."""
        result = utc_iso_from_ms(1724305416000)
        assert result == "2024-08-22T05:43:36Z"
    
    def test_utc_iso_from_ms_edge_cases(self):
        """Testuje hranické případy."""
        # Unix epoch start
        result = utc_iso_from_ms(0)
        assert result == "1970-01-01T00:00:00Z"
        
        # Rok 2000
        result = utc_iso_from_ms(946684800000)
        assert result == "2000-01-01T00:00:00Z"
        
        # Rok 2030
        result = utc_iso_from_ms(1893456000000)
        assert result == "2030-01-01T00:00:00Z"
    
    def test_utc_iso_from_ms_errors(self):
        """Testuje chybové stavy."""
        with pytest.raises(ValueError, match="Timestamp musí být nezáporné"):
            utc_iso_from_ms(-1)


class TestNormalizeCallTask:
    """Testy pro normalize_call_task."""
    
    def test_normalize_call_task_happy_path(self):
        """Testuje základní funkcionalitu."""
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000,
            "tpe": {"type": "CallSessionTask"},
            "result": []
        }
        
        result = normalize_call_task(call_task)
        
        expected = {
            "call_id": "20240822_054336_71da9579",
            "spinoco_call_guid": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "last_update_ms": 1724305416000,
            "call_ts_utc": "2024-08-22T05:43:36Z",
            "raw": call_task
        }
        assert result == expected
    
    def test_normalize_call_task_minimal(self):
        """Testuje minimální CallTask."""
        call_task = {
            "id": "12345678-1234-1234-1234-123456789012",
            "lastUpdate": 1724305416000
        }
        
        result = normalize_call_task(call_task)
        
        assert result["call_id"] == "20240822_054336_12345678"
        assert result["spinoco_call_guid"] == "12345678-1234-1234-1234-123456789012"
        assert result["last_update_ms"] == 1724305416000
        assert result["call_ts_utc"] == "2024-08-22T05:43:36Z"
        assert result["raw"] == call_task
    
    def test_normalize_call_task_errors(self):
        """Testuje chybové stavy."""
        # Prázdný dict
        with pytest.raises(ValueError, match="CallTask musí obsahovat"):
            normalize_call_task({})
        
        # Chybí id
        with pytest.raises(ValueError, match="CallTask musí obsahovat"):
            normalize_call_task({"lastUpdate": 1724305416000})
        
        # Chybí lastUpdate
        with pytest.raises(ValueError, match="CallTask musí obsahovat"):
            normalize_call_task({"id": "test"})
        
        # None
        with pytest.raises(ValueError, match="CallTask musí obsahovat"):
            normalize_call_task(None)


class TestBuildRecordingsMetadata:
    """Testy pro build_recordings_metadata."""
    
    def test_build_recordings_metadata_happy_path(self):
        """Testuje základní funkcionalitu."""
        call_doc = {
            "call_id": "20240822_054336_71da9579",
            "spinoco_call_guid": "71da9579-7730-11ee-9300-a3a8e273fd52"
        }
        
        recordings = [
            {"id": "rec1", "date": 1724305416000, "duration": 120, "available": True},
            {"id": "rec2", "date": 1724305417000, "duration": 90, "available": False}
        ]
        
        result = build_recordings_metadata(call_doc, recordings)
        
        assert len(result) == 2
        
        # První nahrávka (nižší date)
        assert result[0]["recording_id"] == "20240822_054336_71da9579_p01"
        assert result[0]["spinoco_recording_id"] == "rec1"
        assert result[0]["recording_date_ms"] == 1724305416000
        assert result[0]["recording_ts_utc"] == "2024-08-22T05:43:36Z"
        assert result[0]["duration_s"] == 120
        assert result[0]["available"] is True
        
        # Druhá nahrávka (vyšší date)
        assert result[1]["recording_id"] == "20240822_054336_71da9579_p02"
        assert result[1]["spinoco_recording_id"] == "rec2"
        assert result[1]["recording_date_ms"] == 1724305417000
        assert result[1]["recording_ts_utc"] == "2024-08-22T05:43:37Z"
        assert result[1]["duration_s"] == 90
        assert result[1]["available"] is False
    
    def test_build_recordings_metadata_tie_break(self):
        """Testuje tie-break při stejném čase."""
        call_doc = {"call_id": "20240822_054336_71da9579"}
        
        recordings = [
            {"id": "recB", "date": 1724305416000, "duration": 120},
            {"id": "recA", "date": 1724305416000, "duration": 90},  # Stejný čas, menší ID
            {"id": "recC", "date": 1724305417000, "duration": 60}   # Vyšší čas
        ]
        
        result = build_recordings_metadata(call_doc, recordings)
        
        assert len(result) == 3
        
        # Seřazení podle (date, id)
        assert result[0]["recording_id"] == "20240822_054336_71da9579_p01"
        assert result[0]["spinoco_recording_id"] == "recA"  # Menší ID při stejném čase
        
        assert result[1]["recording_id"] == "20240822_054336_71da9579_p02"
        assert result[1]["spinoco_recording_id"] == "recB"  # Větší ID při stejném čase
        
        assert result[2]["recording_id"] == "20240822_054336_71da9579_p03"
        assert result[2]["spinoco_recording_id"] == "recC"  # Vyšší čas
    
    def test_build_recordings_metadata_missing_date(self):
        """Testuje nahrávky bez date."""
        call_doc = {"call_id": "20240822_054336_71da9579"}
        
        recordings = [
            {"id": "rec1", "date": 1724305416000, "duration": 120},
            {"id": "rec2"},  # Chybí date
            {"id": "rec3", "date": None, "duration": 90},  # date je None
            {"id": "rec4", "date": 0, "duration": 60},    # date je 0
            {"id": "rec5", "date": -1, "duration": 30},   # date je záporné
            {"id": "rec6", "date": 1724305417000, "duration": 45}
        ]
        
        result = build_recordings_metadata(call_doc, recordings)
        
        # Měly by se vrátit jen nahrávky s validním date
        assert len(result) == 3
        
        assert result[0]["spinoco_recording_id"] == "rec4"  # date: 0 je nejmenší
        assert result[1]["spinoco_recording_id"] == "rec1"  # date: 1724305416000
        assert result[2]["spinoco_recording_id"] == "rec6"  # date: 1724305417000
        # rec2, rec3, rec5 byly vynechány (chybí date, None, záporné)
    
    def test_build_recordings_metadata_empty(self):
        """Testuje prázdný seznam nahrávek."""
        call_doc = {"call_id": "20240822_054336_71da9579"}
        
        result = build_recordings_metadata(call_doc, [])
        assert result == []
    
    def test_build_recordings_metadata_errors(self):
        """Testuje chybové stavy."""
        # Chybí call_id
        with pytest.raises(ValueError, match="call_doc musí obsahovat"):
            build_recordings_metadata({}, [{"id": "rec1", "date": 1724305416000}])


class TestSpinocoToInternal:
    """Testy pro spinoco_to_internal."""
    
    def test_spinoco_to_internal_happy_path(self):
        """Testuje základní funkcionalitu."""
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000,
            "tpe": {"type": "CallSessionTask"}
        }
        
        recordings = [
            {"id": "rec1", "date": 1724305416000, "duration": 120, "available": True},
            {"id": "rec2", "date": 1724305417000, "duration": 90, "available": False}
        ]
        
        call_meta, recordings_meta = spinoco_to_internal(call_task, recordings)
        
        # Call metadata
        assert call_meta["call_id"] == "20240822_054336_71da9579"
        assert call_meta["spinoco_call_guid"] == "71da9579-7730-11ee-9300-a3a8e273fd52"
        assert call_meta["call_ts_utc"] == "2024-08-22T05:43:36Z"
        
        # Recordings metadata
        assert len(recordings_meta) == 2
        assert recordings_meta[0]["recording_id"] == "20240822_054336_71da9579_p01"
        assert recordings_meta[1]["recording_id"] == "20240822_054336_71da9579_p02"
    
    def test_spinoco_to_internal_no_recordings(self):
        """Testuje call bez nahrávek."""
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000
        }
        
        call_meta, recordings_meta = spinoco_to_internal(call_task, [])
        
        assert call_meta["call_id"] == "20240822_054336_71da9579"
        assert recordings_meta == []


class TestValidators:
    """Testy pro validátory."""
    
    def test_validate_call_task_happy_path(self):
        """Testuje validní CallTask."""
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000
        }
        
        assert validate_call_task(call_task) is True
    
    def test_validate_call_task_invalid(self):
        """Testuje nevalidní CallTask."""
        # Prázdný dict
        assert validate_call_task({}) is False
        
        # Chybí id
        assert validate_call_task({"lastUpdate": 1724305416000}) is False
        
        # Chybí lastUpdate
        assert validate_call_task({"id": "test"}) is False
        
        # None
        assert validate_call_task(None) is False
        
        # Ne-dict
        assert validate_call_task("not a dict") is False
    
    def test_validate_recording_happy_path(self):
        """Testuje validní CallRecording."""
        recording = {
            "id": "rec1",
            "date": 1724305416000,
            "duration": 120
        }
        
        assert validate_recording(recording) is True
    
    def test_validate_recording_invalid(self):
        """Testuje nevalidní CallRecording."""
        # Prázdný dict
        assert validate_recording({}) is False
        
        # Chybí id
        assert validate_recording({"date": 1724305416000}) is False
        
        # None
        assert validate_recording(None) is False
        
        # Ne-dict
        assert validate_recording("not a dict") is False


class TestIntegration:
    """Integrační testy."""
    
    def test_full_workflow(self):
        """Testuje kompletní workflow."""
        # Spinoco data
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000,
            "tpe": {"type": "CallSessionTask"},
            "result": []
        }
        
        recordings = [
            {"id": "recB", "date": 1724305416000, "duration": 120, "available": True},
            {"id": "recA", "date": 1724305416000, "duration": 90, "available": False},
            {"id": "recC", "date": 1724305417000, "duration": 60, "available": True}
        ]
        
        # Převod na interní metadata
        call_meta, recordings_meta = spinoco_to_internal(call_task, recordings)
        
        # Validace call metadata
        assert call_meta["call_id"] == "20240822_054336_71da9579"
        assert call_meta["spinoco_call_guid"] == "71da9579-7730-11ee-9300-a3a8e273fd52"
        assert call_meta["call_ts_utc"] == "2024-08-22T05:43:36Z"
        
        # Validace recordings metadata (deterministic ordering)
        assert len(recordings_meta) == 3
        
        # Seřazení podle (date, id)
        assert recordings_meta[0]["spinoco_recording_id"] == "recA"  # Menší ID při stejném čase
        assert recordings_meta[0]["recording_id"] == "20240822_054336_71da9579_p01"
        
        assert recordings_meta[1]["spinoco_recording_id"] == "recB"  # Větší ID při stejném čase
        assert recordings_meta[1]["recording_id"] == "20240822_054336_71da9579_p02"
        
        assert recordings_meta[2]["spinoco_recording_id"] == "recC"  # Vyšší čas
        assert recordings_meta[2]["recording_id"] == "20240822_054336_71da9579_p03"
        
        # Validace časových razítek
        assert recordings_meta[0]["recording_ts_utc"] == "2024-08-22T05:43:36Z"
        assert recordings_meta[1]["recording_ts_utc"] == "2024-08-22T05:43:36Z"
        assert recordings_meta[2]["recording_ts_utc"] == "2024-08-22T05:43:37Z"
    
    def test_stability(self):
        """Testuje že stejné vstupy dávají stejný výstup."""
        call_task = {
            "id": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "lastUpdate": 1724305416000
        }
        
        recordings = [
            {"id": "recB", "date": 1724305416000, "duration": 120},
            {"id": "recA", "date": 1724305416000, "duration": 90}
        ]
        
        # Dvakrát stejný převod
        call_meta1, recordings_meta1 = spinoco_to_internal(call_task, recordings)
        call_meta2, recordings_meta2 = spinoco_to_internal(call_task, recordings)
        
        # Výsledky musí být identické
        assert call_meta1 == call_meta2
        assert recordings_meta1 == recordings_meta2
        
        # Pořadí musí být deterministické
        assert recordings_meta1[0]["spinoco_recording_id"] == "recA"
        assert recordings_meta1[1]["spinoco_recording_id"] == "recB"
