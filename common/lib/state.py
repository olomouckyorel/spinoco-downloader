"""
State store pro Spinoco pipeline.

Poskytuje idempotentní SQLite databázi pro sledování stavu hovorů a nahrávek,
s retry logikou a robustním error handlingem.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pathlib import Path


class State:
    """
    State store pro Spinoco pipeline.
    
    Ukládá stav hovorů a nahrávek v SQLite databázi s WAL režimem
    a foreign key constraints.
    """
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Inicializuje state store.
        
        Args:
            db_path: Cesta k SQLite databázi
        """
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self._connect()
        self._migrate_if_needed()
    
    def _connect(self) -> None:
        """Vytvoří připojení k databázi s optimálními nastaveními."""
        self._connection = sqlite3.connect(str(self.db_path))
        self._connection.row_factory = sqlite3.Row  # Pro dict-like přístup
        
        # Nastav PRAGMAs pro optimální výkon
        cursor = self._connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    def _migrate_if_needed(self) -> None:
        """Vytvoří tabulky pokud neexistují a nastaví schema verzi."""
        cursor = self._connection.cursor()
        
        # Vytvoř schema_meta tabulku
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Zkontroluj aktuální schema verzi
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'")
        result = cursor.fetchone()
        
        if not result:
            # První spuštění - vytvoř všechny tabulky
            self._create_tables_v1()
            cursor.execute("INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1')")
            self._connection.commit()
        else:
            schema_version = result[0]
            if schema_version != '1':
                raise ValueError(f"Neznámá schema verze: {schema_version}")
        
        cursor.close()
    
    def _create_tables_v1(self) -> None:
        """Vytvoří tabulky pro schema verzi 1."""
        cursor = self._connection.cursor()
        
        # Calls tabulka
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls(
                spinoco_call_guid   TEXT PRIMARY KEY,
                call_id             TEXT NOT NULL,
                last_update_ms      INTEGER NOT NULL,
                seen_at_utc         TEXT NOT NULL
            )
        """)
        
        # Recordings tabulka
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordings(
                spinoco_recording_id   TEXT PRIMARY KEY,
                spinoco_call_guid      TEXT NOT NULL,
                recording_id           TEXT NOT NULL,
                recording_date_ms      INTEGER NOT NULL,
                size_bytes             INTEGER,
                content_etag           TEXT,
                status                 TEXT NOT NULL DEFAULT 'pending',
                retry_count            INTEGER NOT NULL DEFAULT 0,
                last_error             TEXT,
                last_error_at_utc     TEXT,
                last_processed_at_utc  TEXT,
                FOREIGN KEY (spinoco_call_guid) REFERENCES calls(spinoco_call_guid)
            )
        """)
        
        # Indexy
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recordings_call ON recordings(spinoco_call_guid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recordings_status ON recordings(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recordings_date ON recordings(recording_date_ms)")
        
        cursor.close()
    
    def close(self) -> None:
        """Zavře připojení k databázi."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # ---- Calls ----
    
    def upsert_call(self, spinoco_call_guid: str, call_id: str, last_update_ms: int, seen_at_utc: str) -> str:
        """
        Vloží nebo aktualizuje záznam hovoru.
        
        Args:
            spinoco_call_guid: Spinoco call GUID
            call_id: Náš call_id
            last_update_ms: UTC timestamp v ms
            seen_at_utc: ISO timestamp kdy jsme to viděli
            
        Returns:
            str: 'inserted' | 'updated' | 'unchanged'
        """
        cursor = self._connection.cursor()
        
        # Zkontroluj existující záznam
        cursor.execute("""
            SELECT last_update_ms FROM calls WHERE spinoco_call_guid = ?
        """, (spinoco_call_guid,))
        
        existing = cursor.fetchone()
        
        if not existing:
            # Nový záznam
            cursor.execute("""
                INSERT INTO calls (spinoco_call_guid, call_id, last_update_ms, seen_at_utc)
                VALUES (?, ?, ?, ?)
            """, (spinoco_call_guid, call_id, last_update_ms, seen_at_utc))
            self._connection.commit()
            cursor.close()
            return 'inserted'
        
        existing_last_update = existing[0]
        
        if last_update_ms > existing_last_update:
            # Aktualizace
            cursor.execute("""
                UPDATE calls 
                SET call_id = ?, last_update_ms = ?, seen_at_utc = ?
                WHERE spinoco_call_guid = ?
            """, (call_id, last_update_ms, seen_at_utc, spinoco_call_guid))
            self._connection.commit()
            cursor.close()
            return 'updated'
        else:
            # Žádná změna
            cursor.close()
            return 'unchanged'
    
    def get_call(self, spinoco_call_guid: str) -> Optional[Dict[str, Any]]:
        """
        Získá záznam hovoru.
        
        Args:
            spinoco_call_guid: Spinoco call GUID
            
        Returns:
            dict nebo None pokud neexistuje
        """
        cursor = self._connection.cursor()
        cursor.execute("""
            SELECT * FROM calls WHERE spinoco_call_guid = ?
        """, (spinoco_call_guid,))
        
        row = cursor.fetchone()
        cursor.close()
        
        return dict(row) if row else None
    
    # ---- Recordings ----
    
    def upsert_recording(self,
                         spinoco_recording_id: str,
                         spinoco_call_guid: str,
                         recording_id: str,
                         recording_date_ms: int,
                         size_bytes: Optional[int] = None,
                         content_etag: Optional[str] = None) -> str:
        """
        Vloží nebo aktualizuje díl nahrávky.
        
        Args:
            spinoco_recording_id: Spinoco recording ID
            spinoco_call_guid: Spinoco call GUID
            recording_id: Náš recording_id
            recording_date_ms: UTC timestamp v ms
            size_bytes: Velikost souboru v bytech
            content_etag: Hash/etag souboru
            
        Returns:
            str: 'inserted' | 'updated' | 'unchanged'
        """
        cursor = self._connection.cursor()
        
        # Zkontroluj existující záznam
        cursor.execute("""
            SELECT size_bytes, content_etag FROM recordings 
            WHERE spinoco_recording_id = ?
        """, (spinoco_recording_id,))
        
        existing = cursor.fetchone()
        
        if not existing:
            # Nový záznam
            cursor.execute("""
                INSERT INTO recordings (
                    spinoco_recording_id, spinoco_call_guid, recording_id,
                    recording_date_ms, size_bytes, content_etag
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (spinoco_recording_id, spinoco_call_guid, recording_id,
                  recording_date_ms, size_bytes, content_etag))
            self._connection.commit()
            cursor.close()
            return 'inserted'
        
        existing_size = existing[0]
        existing_etag = existing[1]
        
        # Zkontroluj změny
        if size_bytes != existing_size or content_etag != existing_etag:
            # Aktualizace
            cursor.execute("""
                UPDATE recordings 
                SET size_bytes = ?, content_etag = ?
                WHERE spinoco_recording_id = ?
            """, (size_bytes, content_etag, spinoco_recording_id))
            self._connection.commit()
            cursor.close()
            return 'updated'
        else:
            # Žádná změna
            cursor.close()
            return 'unchanged'
    
    def mark_downloaded(self, spinoco_recording_id: str, size_bytes: Optional[int], 
                       content_etag: Optional[str], processed_at_utc: str) -> None:
        """
        Označí nahrávku jako staženou.
        
        Args:
            spinoco_recording_id: Spinoco recording ID
            size_bytes: Velikost staženého souboru
            content_etag: Hash/etag staženého souboru
            processed_at_utc: ISO timestamp zpracování
        """
        cursor = self._connection.cursor()
        cursor.execute("""
            UPDATE recordings 
            SET status = 'downloaded', 
                size_bytes = ?, 
                content_etag = ?, 
                last_processed_at_utc = ?,
                last_error = NULL,
                last_error_at_utc = NULL
            WHERE spinoco_recording_id = ?
        """, (size_bytes, content_etag, processed_at_utc, spinoco_recording_id))
        self._connection.commit()
        cursor.close()
    
    def mark_failed_transient(self, spinoco_recording_id: str, error_key: str, failed_at_utc: str) -> int:
        """
        Označí nahrávku jako dočasně selhanou.
        
        Args:
            spinoco_recording_id: Spinoco recording ID
            error_key: Klíč chyby (např. 'network_error', 'checksum_mismatch')
            failed_at_utc: ISO timestamp selhání
            
        Returns:
            int: Nový retry_count
        """
        cursor = self._connection.cursor()
        
        # Získej aktuální retry_count
        cursor.execute("""
            SELECT retry_count FROM recordings WHERE spinoco_recording_id = ?
        """, (spinoco_recording_id,))
        
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Recording {spinoco_recording_id} neexistuje")
        
        new_retry_count = result[0] + 1
        
        # Aktualizuj status a retry_count
        cursor.execute("""
            UPDATE recordings 
            SET status = 'failed-transient',
                retry_count = ?,
                last_error = ?,
                last_error_at_utc = ?
            WHERE spinoco_recording_id = ?
        """, (new_retry_count, error_key, failed_at_utc, spinoco_recording_id))
        
        self._connection.commit()
        cursor.close()
        
        return new_retry_count
    
    def mark_failed_permanent(self, spinoco_recording_id: str, error_key: str, failed_at_utc: str) -> None:
        """
        Označí nahrávku jako trvale selhanou.
        
        Args:
            spinoco_recording_id: Spinoco recording ID
            error_key: Klíč chyby
            failed_at_utc: ISO timestamp selhání
        """
        cursor = self._connection.cursor()
        cursor.execute("""
            UPDATE recordings 
            SET status = 'failed-permanent',
                last_error = ?,
                last_error_at_utc = ?
            WHERE spinoco_recording_id = ?
        """, (error_key, failed_at_utc, spinoco_recording_id))
        self._connection.commit()
        cursor.close()
    
    def quarantine(self, spinoco_recording_id: str, error_key: str, at_utc: str) -> None:
        """
        Přesune nahrávku do karantény.
        
        Args:
            spinoco_recording_id: Spinoco recording ID
            error_key: Klíč chyby
            at_utc: ISO timestamp karantény
        """
        cursor = self._connection.cursor()
        cursor.execute("""
            UPDATE recordings 
            SET status = 'quarantined',
                last_error = ?,
                last_error_at_utc = ?
            WHERE spinoco_recording_id = ?
        """, (error_key, at_utc, spinoco_recording_id))
        self._connection.commit()
        cursor.close()
    
    # ---- Výběry pro práci kroku ----
    
    def list_recordings_by_status(self, statuses: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Vrátí nahrávky podle statusu.
        
        Args:
            statuses: Seznam statusů
            limit: Maximální počet výsledků
            
        Returns:
            List[Dict]: Seznam nahrávek
        """
        cursor = self._connection.cursor()
        
        placeholders = ','.join(['?' for _ in statuses])
        query = f"""
            SELECT * FROM recordings 
            WHERE status IN ({placeholders})
            ORDER BY recording_date_ms ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, statuses)
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def list_todo_for_download(self, max_retry: int = 3, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Vrátí nahrávky připravené ke stažení.
        
        Args:
            max_retry: Maximální počet retry
            limit: Maximální počet výsledků
            
        Returns:
            List[Dict]: Seznam nahrávek k stažení
        """
        cursor = self._connection.cursor()
        
        query = """
            SELECT * FROM recordings 
            WHERE (status = 'pending' OR 
                   (status = 'failed-transient' AND retry_count < ?))
            ORDER BY recording_date_ms ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (max_retry,))
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def list_changed_or_unknown(self, expected_size: Optional[int] = None, 
                               expected_etag: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Vrátí nahrávky kde se liší velikost nebo etag.
        
        Args:
            expected_size: Očekávaná velikost
            expected_etag: Očekávaný etag
            
        Returns:
            List[Dict]: Seznam nahrávek s rozdíly
        """
        cursor = self._connection.cursor()
        
        conditions = []
        params = []
        
        if expected_size is not None:
            conditions.append("(size_bytes IS NULL OR size_bytes != ?)")
            params.append(expected_size)
        
        if expected_etag is not None:
            conditions.append("(content_etag IS NULL OR content_etag != ?)")
            params.append(expected_etag)
        
        if not conditions:
            # Pokud nejsou specifikovány očekávané hodnoty, vrať všechny
            cursor.execute("SELECT * FROM recordings ORDER BY recording_date_ms ASC")
        else:
            query = f"""
                SELECT * FROM recordings 
                WHERE {' OR '.join(conditions)}
                ORDER BY recording_date_ms ASC
            """
            cursor.execute(query, params)
        
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Vrátí statistiky databáze.
        
        Returns:
            Dict: Statistiky
        """
        cursor = self._connection.cursor()
        
        # Počty podle statusu
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM recordings 
            GROUP BY status
        """)
        status_counts = dict(cursor.fetchall())
        
        # Celkové počty
        cursor.execute("SELECT COUNT(*) FROM calls")
        total_calls = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM recordings")
        total_recordings = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            'total_calls': total_calls,
            'total_recordings': total_recordings,
            'status_counts': status_counts
        }
