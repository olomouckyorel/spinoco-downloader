"""
Unit testy pro common/lib/ids.py
"""

import pytest
from datetime import datetime
from lib.ids import (
    new_ulid, new_run_id, call_id_from_spinoco, make_recording_ids,
    is_valid_call_id, is_valid_run_id, timestamp_from_call_id, extract_call_id_base
)


class TestULID:
    """Testy pro ULID generátory."""
    
    def test_new_ulid_format(self):
        """Testuje formát ULID."""
        ulid_str = new_ulid()
        assert len(ulid_str) == 26
        assert ulid_str.isalnum()
        # Crockford Base32: 0-9, A-Z (bez I, L, O, U)
        assert all(c in '0123456789ABCDEFGHJKLMNPQRSTVWXYZ' for c in ulid_str)
    
    def test_new_run_id(self):
        """Testuje že new_run_id() je alias pro new_ulid()."""
        run_id = new_run_id()
        assert len(run_id) == 26
        assert is_valid_run_id(run_id)
    
    def test_ulid_sortable(self):
        """Testuje že ULID jsou lexikograficky řaditelné."""
        ulids = [new_ulid() for _ in range(10)]
        sorted_ulids = sorted(ulids)
        assert ulids != sorted_ulids  # Původní není seřazené
        assert min(ulids) == sorted_ulids[0]  # Min je první v seřazeném


class TestCallID:
    """Testy pro call_id generátory."""
    
    def test_call_id_from_spinoco_happy_path(self):
        """Testuje základní funkcionalitu call_id_from_spinoco."""
        # Test s konkrétním timestampem
        result = call_id_from_spinoco(1724305416000, "71da9579-7730-11ee-9300-a3a8e273fd52")
        assert result == "20240822_054336_71da9579"
    
    def test_call_id_from_spinoco_edge_cases(self):
        """Testuje hranické případy."""
        # Minimální GUID
        result = call_id_from_spinoco(1724305416000, "12345678")
        assert result == "20240822_054336_12345678"
        
        # Delší GUID
        result = call_id_from_spinoco(1724305416000, "71da9579-7730-11ee-9300-a3a8e273fd52-extra")
        assert result == "20240822_054336_71da9579"
    
    def test_call_id_from_spinoco_errors(self):
        """Testuje chybové stavy."""
        # Prázdný GUID
        with pytest.raises(ValueError, match="call_guid musí mít alespoň 8 znaků"):
            call_id_from_spinoco(1724305416000, "")
        
        # Krátký GUID
        with pytest.raises(ValueError, match="call_guid musí mít alespoň 8 znaků"):
            call_id_from_spinoco(1724305416000, "1234567")
        
        # Nevalidní timestamp
        with pytest.raises(ValueError, match="last_update_ms musí být kladné"):
            call_id_from_spinoco(0, "71da9579-7730-11ee-9300-a3a8e273fd52")
        
        with pytest.raises(ValueError, match="last_update_ms musí být kladné"):
            call_id_from_spinoco(-1, "71da9579-7730-11ee-9300-a3a8e273fd52")


class TestRecordingIDs:
    """Testy pro recording_id generátory."""
    
    def test_make_recording_ids_happy_path(self):
        """Testuje základní funkcionalitu make_recording_ids."""
        call_id = "20240822_063016_71da9579"
        recordings = [
            {'id': 'B', 'date': 2},
            {'id': 'A', 'date': 2}, 
            {'id': 'C', 'date': 3}
        ]
        
        result = make_recording_ids(call_id, recordings)
        
        expected = {
            'A': '20240822_063016_71da9579_p01',  # Nejmenší ID při stejném čase
            'B': '20240822_063016_71da9579_p02',  # Druhý při stejném čase
            'C': '20240822_063016_71da9579_p03'   # Nejvyšší čas
        }
        assert result == expected
    
    def test_make_recording_ids_empty(self):
        """Testuje prázdný seznam nahrávek."""
        result = make_recording_ids("20240822_063016_71da9579", [])
        assert result == {}
    
    def test_make_recording_ids_single(self):
        """Testuje jednu nahrávku."""
        call_id = "20240822_063016_71da9579"
        recordings = [{'id': 'single', 'date': 1}]
        
        result = make_recording_ids(call_id, recordings)
        assert result == {'single': '20240822_063016_71da9579_p01'}
    
    def test_make_recording_ids_missing_fields(self):
        """Testuje nahrávky s chybějícími poli."""
        call_id = "20240822_063016_71da9579"
        recordings = [
            {'id': 'A'},  # Chybí date
            {'id': 'B', 'date': 1}
        ]
        
        result = make_recording_ids(call_id, recordings)
        # A má date=0 (default), B má date=1, takže A bude první
        assert result == {
            'A': '20240822_063016_71da9579_p01',
            'B': '20240822_063016_71da9579_p02'
        }
    
    def test_make_recording_ids_errors(self):
        """Testuje chybové stavy."""
        # Prázdný call_id
        with pytest.raises(ValueError, match="call_id nesmí být prázdný"):
            make_recording_ids("", [{'id': 'A', 'date': 1}])


class TestValidators:
    """Testy pro validátory."""
    
    def test_is_valid_call_id_happy_path(self):
        """Testuje validní call_id."""
        valid_ids = [
            "20240822_054336_71da9579",
            "20241231_235959_abcdef12",
            "20240101_000000_00000000"
        ]
        
        for call_id in valid_ids:
            assert is_valid_call_id(call_id), f"Should be valid: {call_id}"
    
    def test_is_valid_call_id_invalid(self):
        """Testuje nevalidní call_id."""
        invalid_ids = [
            "",  # Prázdný
            "20240822_054336",  # Chybí base
            "20240822_054336_71da9579_extra",  # Příliš dlouhý
            "20240822_054336_71da95",  # Base příliš krátký
            "20240822_054336_71da957@",  # Nevalidní znak v base
            "2024082_054336_71da9579",  # Datum příliš krátké
            "20240822_05433_71da9579",  # Čas příliš krátký
            "20240822054336_71da9579",  # Chybí podtržítko
            None,  # None
            123,  # Ne-string
        ]
        
        for call_id in invalid_ids:
            assert not is_valid_call_id(call_id), f"Should be invalid: {call_id}"
    
    def test_is_valid_run_id_happy_path(self):
        """Testuje validní run_id."""
        run_id = new_run_id()
        assert is_valid_run_id(run_id)
        
        # Test s konkrétním ULID
        assert is_valid_run_id("01J9ZC3AC9V2J9FZK2C3R8K9TQ")
    
    def test_is_valid_run_id_invalid(self):
        """Testuje nevalidní run_id."""
        invalid_ids = [
            "",  # Prázdný
            "01J9ZC3AC9V2J9FZK2C3R8K9T",  # Příliš krátký
            "01J9ZC3AC9V2J9FZK2C3R8K9TQQ",  # Příliš dlouhý
            "01J9ZC3AC9V2J9FZK2C3R8K9TIQ",  # Obsahuje 'I'
            "01J9ZC3AC9V2J9FZK2C3R8K9TLQ",  # Obsahuje 'L'
            "01J9ZC3AC9V2J9FZK2C3R8K9TOQ",  # Obsahuje 'O'
            "01J9ZC3AC9V2J9FZK2C3R8K9TUQ",  # Obsahuje 'U'
            None,  # None
            123,  # Ne-string
        ]
        
        for run_id in invalid_ids:
            assert not is_valid_run_id(run_id), f"Should be invalid: {run_id}"


class TestExtractors:
    """Testy pro extraktory."""
    
    def test_timestamp_from_call_id(self):
        """Testuje extrakci timestampu z call_id."""
        call_id = "20240822_054336_71da9579"
        result = timestamp_from_call_id(call_id)
        
        expected = datetime(2024, 8, 22, 5, 43, 36)
        assert result == expected
    
    def test_timestamp_from_call_id_invalid(self):
        """Testuje chybu při nevalidním call_id."""
        with pytest.raises(ValueError, match="Nevalidní call_id"):
            timestamp_from_call_id("invalid")
    
    def test_extract_call_id_base(self):
        """Testuje extrakci base části z call_id."""
        call_id = "20240822_054336_71da9579"
        result = extract_call_id_base(call_id)
        assert result == "71da9579"
    
    def test_extract_call_id_base_invalid(self):
        """Testuje chybu při nevalidním call_id."""
        with pytest.raises(ValueError, match="Nevalidní call_id"):
            extract_call_id_base("invalid")


class TestIntegration:
    """Integrační testy."""
    
    def test_full_workflow(self):
        """Testuje kompletní workflow."""
        # 1. Generuj call_id
        call_id = call_id_from_spinoco(1724305416000, "71da9579-7730-11ee-9300-a3a8e273fd52")
        assert call_id == "20240822_054336_71da9579"
        
        # 2. Validuj call_id
        assert is_valid_call_id(call_id)
        
        # 3. Extrahuj timestamp
        timestamp = timestamp_from_call_id(call_id)
        assert timestamp.year == 2024
        assert timestamp.month == 8
        assert timestamp.day == 22
        
        # 4. Extrahuj base
        base = extract_call_id_base(call_id)
        assert base == "71da9579"
        
        # 5. Generuj recording_ids
        recordings = [
            {'id': 'rec1', 'date': 1724305416000},
            {'id': 'rec2', 'date': 1724305417000}
        ]
        recording_ids = make_recording_ids(call_id, recordings)
        
        expected = {
            'rec1': '20240822_054336_71da9579_p01',
            'rec2': '20240822_054336_71da9579_p02'
        }
        assert recording_ids == expected
        
        # 6. Generuj run_id
        run_id = new_run_id()
        assert is_valid_run_id(run_id)
        assert len(run_id) == 26
