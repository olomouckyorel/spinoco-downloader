"""
Unit testy pro common/lib/state.py
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from common.lib.state import State


class TestStateInit:
    """Testy pro inicializaci State."""
    
    def test_init_creates_db_and_tables(self):
        """Testuje že inicializace vytvoří DB a tabulky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Zkontroluj že tabulky existují
                cursor = state._connection.cursor()
                
                # Schema meta
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'")
                assert cursor.fetchone() is not None
                
                # Calls
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calls'")
                assert cursor.fetchone() is not None
                
                # Recordings
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'")
                assert cursor.fetchone() is not None
                
                # Indexy
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_recordings_call'")
                assert cursor.fetchone() is not None
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_recordings_status'")
                assert cursor.fetchone() is not None
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_recordings_date'")
                assert cursor.fetchone() is not None
                
                cursor.close()
    
    def test_schema_version_stored(self):
        """Testuje že schema verze je uložena."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                cursor = state._connection.cursor()
                cursor.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'")
                result = cursor.fetchone()
                assert result[0] == '1'
                cursor.close()
    
    def test_pragmas_set(self):
        """Testuje že PRAGMAs jsou nastaveny."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                cursor = state._connection.cursor()
                
                # Journal mode
                cursor.execute("PRAGMA journal_mode")
                assert cursor.fetchone()[0] == 'wal'
                
                # Synchronous
                cursor.execute("PRAGMA synchronous")
                assert cursor.fetchone()[0] == 1  # NORMAL
                
                # Foreign keys
                cursor.execute("PRAGMA foreign_keys")
                assert cursor.fetchone()[0] == 1  # ON
                
                cursor.close()


class TestCalls:
    """Testy pro calls operace."""
    
    def test_upsert_call_inserted(self):
        """Testuje vložení nového hovoru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                result = state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                assert result == 'inserted'
                
                # Zkontroluj že záznam existuje
                call = state.get_call("71da9579-7730-11ee-9300-a3a8e273fd52")
                assert call is not None
                assert call['call_id'] == "20240822_054336_71da9579"
                assert call['last_update_ms'] == 1724305416000
                assert call['seen_at_utc'] == "2024-08-22T05:43:36Z"
    
    def test_upsert_call_updated(self):
        """Testuje aktualizaci hovoru s vyšším last_update_ms."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # První vložení
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                # Aktualizace s vyšším timestampem
                result = state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305417000,  # Vyšší timestamp
                    "2024-08-22T05:43:37Z"
                )
                
                assert result == 'updated'
                
                # Zkontroluj aktualizaci
                call = state.get_call("71da9579-7730-11ee-9300-a3a8e273fd52")
                assert call['last_update_ms'] == 1724305417000
                assert call['seen_at_utc'] == "2024-08-22T05:43:37Z"
    
    def test_upsert_call_unchanged(self):
        """Testuje že stejný timestamp nezpůsobí změnu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # První vložení
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                # Stejný timestamp
                result = state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,  # Stejný timestamp
                    "2024-08-22T05:43:36Z"
                )
                
                assert result == 'unchanged'
    
    def test_get_call_nonexistent(self):
        """Testuje získání neexistujícího hovoru."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                call = state.get_call("nonexistent-guid")
                assert call is None


class TestRecordings:
    """Testy pro recordings operace."""
    
    def test_upsert_recording_inserted(self):
        """Testuje vložení nové nahrávky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Nejdřív vytvoř call
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                result = state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000,
                    size_bytes=1024,
                    content_etag="abc123"
                )
                
                assert result == 'inserted'
                
                # Zkontroluj že záznam existuje
                recordings = state.list_recordings_by_status(['pending'])
                assert len(recordings) == 1
                assert recordings[0]['spinoco_recording_id'] == 'rec1'
                assert recordings[0]['status'] == 'pending'
                assert recordings[0]['size_bytes'] == 1024
                assert recordings[0]['content_etag'] == 'abc123'
    
    def test_upsert_recording_updated(self):
        """Testuje aktualizaci nahrávky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Nejdřív vytvoř call
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                # První vložení
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000,
                    size_bytes=1024,
                    content_etag="abc123"
                )
                
                # Aktualizace s jinou velikostí
                result = state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000,
                    size_bytes=2048,  # Jiná velikost
                    content_etag="def456"  # Jiný etag
                )
                
                assert result == 'updated'
                
                # Zkontroluj aktualizaci
                recordings = state.list_recordings_by_status(['pending'])
                assert recordings[0]['size_bytes'] == 2048
                assert recordings[0]['content_etag'] == 'def456'
    
    def test_upsert_recording_unchanged(self):
        """Testuje že stejné hodnoty nezpůsobí změnu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Nejdřív vytvoř call
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                # První vložení
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000,
                    size_bytes=1024,
                    content_etag="abc123"
                )
                
                # Stejné hodnoty
                result = state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000,
                    size_bytes=1024,  # Stejná velikost
                    content_etag="abc123"  # Stejný etag
                )
                
                assert result == 'unchanged'


class TestStatusOperations:
    """Testy pro operace se statusy."""
    
    def test_mark_downloaded(self):
        """Testuje označení nahrávky jako stažené."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000
                )
                
                # Označ jako stažené
                state.mark_downloaded(
                    "rec1",
                    size_bytes=1024,
                    content_etag="abc123",
                    processed_at_utc="2024-08-22T05:44:00Z"
                )
                
                # Zkontroluj změny
                recordings = state.list_recordings_by_status(['downloaded'])
                assert len(recordings) == 1
                assert recordings[0]['status'] == 'downloaded'
                assert recordings[0]['size_bytes'] == 1024
                assert recordings[0]['content_etag'] == 'abc123'
                assert recordings[0]['last_processed_at_utc'] == '2024-08-22T05:44:00Z'
                assert recordings[0]['last_error'] is None
                assert recordings[0]['last_error_at_utc'] is None
    
    def test_mark_failed_transient(self):
        """Testuje označení nahrávky jako dočasně selhané."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000
                )
                
                # Označ jako selhané
                retry_count = state.mark_failed_transient(
                    "rec1",
                    error_key="network_error",
                    failed_at_utc="2024-08-22T05:44:00Z"
                )
                
                assert retry_count == 1
                
                # Zkontroluj změny
                recordings = state.list_recordings_by_status(['failed-transient'])
                assert len(recordings) == 1
                assert recordings[0]['status'] == 'failed-transient'
                assert recordings[0]['retry_count'] == 1
                assert recordings[0]['last_error'] == 'network_error'
                assert recordings[0]['last_error_at_utc'] == '2024-08-22T05:44:00Z'
    
    def test_mark_failed_transient_multiple(self):
        """Testuje více retry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000
                )
                
                # První retry
                retry_count = state.mark_failed_transient(
                    "rec1",
                    error_key="network_error",
                    failed_at_utc="2024-08-22T05:44:00Z"
                )
                assert retry_count == 1
                
                # Druhý retry
                retry_count = state.mark_failed_transient(
                    "rec1",
                    error_key="timeout",
                    failed_at_utc="2024-08-22T05:45:00Z"
                )
                assert retry_count == 2
                
                # Zkontroluj finální stav
                recordings = state.list_recordings_by_status(['failed-transient'])
                assert recordings[0]['retry_count'] == 2
                assert recordings[0]['last_error'] == 'timeout'
    
    def test_mark_failed_permanent(self):
        """Testuje označení nahrávky jako trvale selhané."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000
                )
                
                # Označ jako trvale selhané
                state.mark_failed_permanent(
                    "rec1",
                    error_key="404_not_found",
                    failed_at_utc="2024-08-22T05:44:00Z"
                )
                
                # Zkontroluj změny
                recordings = state.list_recordings_by_status(['failed-permanent'])
                assert len(recordings) == 1
                assert recordings[0]['status'] == 'failed-permanent'
                assert recordings[0]['last_error'] == '404_not_found'
    
    def test_quarantine(self):
        """Testuje přesunutí nahrávky do karantény."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording(
                    "rec1",
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579_p01",
                    1724305416000
                )
                
                # Přesuň do karantény
                state.quarantine(
                    "rec1",
                    error_key="corrupted_file",
                    at_utc="2024-08-22T05:44:00Z"
                )
                
                # Zkontroluj změny
                recordings = state.list_recordings_by_status(['quarantined'])
                assert len(recordings) == 1
                assert recordings[0]['status'] == 'quarantined'
                assert recordings[0]['last_error'] == 'corrupted_file'


class TestQueries:
    """Testy pro dotazy."""
    
    def test_list_todo_for_download(self):
        """Testuje výběr nahrávek k stažení."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup calls
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                # Různé statusy
                state.upsert_recording("rec1", "71da9579-7730-11ee-9300-a3a8e273fd52", "p01", 1724305416000)
                state.upsert_recording("rec2", "71da9579-7730-11ee-9300-a3a8e273fd52", "p02", 1724305417000)
                state.upsert_recording("rec3", "71da9579-7730-11ee-9300-a3a8e273fd52", "p03", 1724305418000)
                
                # Označ některé jako stažené
                state.mark_downloaded("rec2", 1024, "abc123", "2024-08-22T05:44:00Z")
                
                # Označ některé jako selhané
                state.mark_failed_transient("rec3", "network_error", "2024-08-22T05:44:00Z")
                
                # Získej TODO
                todo = state.list_todo_for_download(max_retry=3)
                
                # Měly by být jen pending a failed-transient s retry < max_retry
                assert len(todo) == 2
                todo_ids = [r['spinoco_recording_id'] for r in todo]
                assert 'rec1' in todo_ids  # pending
                assert 'rec3' in todo_ids  # failed-transient s retry=1 < 3
                assert 'rec2' not in todo_ids  # downloaded
    
    def test_list_todo_for_download_max_retry(self):
        """Testuje že nahrávky s max retry se nevrátí."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording("rec1", "71da9579-7730-11ee-9300-a3a8e273fd52", "p01", 1724305416000)
                
                # Označ jako selhané vícekrát
                state.mark_failed_transient("rec1", "error1", "2024-08-22T05:44:00Z")  # retry=1
                state.mark_failed_transient("rec1", "error2", "2024-08-22T05:45:00Z")  # retry=2
                state.mark_failed_transient("rec1", "error3", "2024-08-22T05:46:00Z")  # retry=3
                
                # Získej TODO s max_retry=3
                todo = state.list_todo_for_download(max_retry=3)
                assert len(todo) == 0  # retry=3 není < 3
                
                # Získej TODO s max_retry=4
                todo = state.list_todo_for_download(max_retry=4)
                assert len(todo) == 1  # retry=3 je < 4
    
    def test_list_recordings_by_status(self):
        """Testuje výběr podle statusu."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording("rec1", "71da9579-7730-11ee-9300-a3a8e273fd52", "p01", 1724305416000)
                state.upsert_recording("rec2", "71da9579-7730-11ee-9300-a3a8e273fd52", "p02", 1724305417000)
                
                state.mark_downloaded("rec1", 1024, "abc123", "2024-08-22T05:44:00Z")
                
                # Získej podle statusu
                pending = state.list_recordings_by_status(['pending'])
                downloaded = state.list_recordings_by_status(['downloaded'])
                
                assert len(pending) == 1
                assert pending[0]['spinoco_recording_id'] == 'rec2'
                
                assert len(downloaded) == 1
                assert downloaded[0]['spinoco_recording_id'] == 'rec1'
    
    def test_list_changed_or_unknown(self):
        """Testuje výběr nahrávek s rozdíly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                
                state.upsert_recording("rec1", "71da9579-7730-11ee-9300-a3a8e273fd52", "p01", 1724305416000, size_bytes=1024, content_etag="abc123")
                state.upsert_recording("rec2", "71da9579-7730-11ee-9300-a3a8e273fd52", "p02", 1724305417000, size_bytes=2048, content_etag="def456")
                
                # Získej s rozdíly
                changed = state.list_changed_or_unknown(expected_size=1024, expected_etag="abc123")
                
                # rec1 má stejné hodnoty, rec2 má jiné
                assert len(changed) == 1
                assert changed[0]['spinoco_recording_id'] == 'rec2'


class TestStats:
    """Testy pro statistiky."""
    
    def test_get_stats(self):
        """Testuje získání statistik."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Setup
                state.upsert_call("call1", "call_id_1", 1724305416000, "2024-08-22T05:43:36Z")
                state.upsert_call("call2", "call_id_2", 1724305417000, "2024-08-22T05:43:37Z")
                
                state.upsert_recording("rec1", "call1", "p01", 1724305416000)
                state.upsert_recording("rec2", "call1", "p02", 1724305417000)
                state.upsert_recording("rec3", "call2", "p01", 1724305418000)
                
                state.mark_downloaded("rec1", 1024, "abc123", "2024-08-22T05:44:00Z")
                state.mark_failed_transient("rec2", "error", "2024-08-22T05:44:00Z")
                
                # Získej statistiky
                stats = state.get_stats()
                
                assert stats['total_calls'] == 2
                assert stats['total_recordings'] == 3
                assert stats['status_counts']['downloaded'] == 1
                assert stats['status_counts']['failed-transient'] == 1
                assert stats['status_counts']['pending'] == 1


class TestIntegration:
    """Integrační testy."""
    
    def test_full_workflow(self):
        """Testuje kompletní workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # 1. Vytvoř call
                result = state.upsert_call(
                    "71da9579-7730-11ee-9300-a3a8e273fd52",
                    "20240822_054336_71da9579",
                    1724305416000,
                    "2024-08-22T05:43:36Z"
                )
                assert result == 'inserted'
                
                # 2. Vytvoř recordings
                state.upsert_recording("rec1", "71da9579-7730-11ee-9300-a3a8e273fd52", "p01", 1724305416000)
                state.upsert_recording("rec2", "71da9579-7730-11ee-9300-a3a8e273fd52", "p02", 1724305417000)
                
                # 3. Získej TODO
                todo = state.list_todo_for_download()
                assert len(todo) == 2
                
                # 4. Označ první jako stažené
                state.mark_downloaded("rec1", 1024, "abc123", "2024-08-22T05:44:00Z")
                
                # 5. Označ druhou jako selhanou
                retry_count = state.mark_failed_transient("rec2", "network_error", "2024-08-22T05:44:00Z")
                assert retry_count == 1
                
                # 6. Získej nové TODO
                todo = state.list_todo_for_download()
                assert len(todo) == 1  # Jen rec2
                assert todo[0]['spinoco_recording_id'] == 'rec2'
                
                # 7. Získej statistiky
                stats = state.get_stats()
                assert stats['total_calls'] == 1
                assert stats['total_recordings'] == 2
                assert stats['status_counts']['downloaded'] == 1
                assert stats['status_counts']['failed-transient'] == 1
    
    def test_stability(self):
        """Testuje že opakované operace dávají deterministické výsledky."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            with State(db_path) as state:
                # Opakované operace
                for i in range(3):
                    state.upsert_call("call1", "call_id_1", 1724305416000, "2024-08-22T05:43:36Z")
                    state.upsert_recording("rec1", "call1", "p01", 1724305416000)
                
                # Výsledky musí být konzistentní
                calls = state.list_recordings_by_status(['pending'])
                assert len(calls) == 1
                
                # Opakované TODO dotazy
                todo1 = state.list_todo_for_download()
                todo2 = state.list_todo_for_download()
                assert todo1 == todo2
