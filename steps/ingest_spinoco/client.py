"""
Spinoco API client pro steps/01_ingest_spinoco.

Obsahuje jak reálný SpinocoClient tak FakeSpinocoClient pro testy.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SpinocoClient:
    """Reálný Spinoco API client."""
    
    def __init__(self, api_base_url: str, token: str, page_size: int = 100):
        self.api_base_url = api_base_url.rstrip('/')
        self.token = token
        self.page_size = page_size
        
        # Nastav HTTP session s retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Auth header
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    
    def list_calls(self, since: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """
        Načte seznam hovorů ze Spinoco API.
        
        Args:
            since: ISO timestamp pro filtrování (volitelné)
            limit: Maximální počet hovorů (volitelné)
            
        Yields:
            Dict: CallTask data
        """
        page = 0
        count = 0
        
        while True:
            params = {
                'page': page,
                'size': self.page_size
            }
            
            if since:
                params['since'] = since
            
            try:
                response = self.session.get(f"{self.api_base_url}/calls", params=params)
                response.raise_for_status()
                
                data = response.json()
                calls = data.get('data', [])
                
                if not calls:
                    break
                
                for call in calls:
                    if limit and count >= limit:
                        return
                    yield call
                    count += 1
                
                page += 1
                
            except requests.RequestException as e:
                raise RuntimeError(f"Chyba při načítání hovorů: {e}")
    
    def list_recordings(self, call_guid: str) -> List[Dict[str, Any]]:
        """
        Načte nahrávky pro konkrétní hovor.
        
        Args:
            call_guid: GUID hovoru
            
        Returns:
            List[Dict]: Seznam nahrávek
        """
        try:
            response = self.session.get(f"{self.api_base_url}/calls/{call_guid}/recordings")
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', [])
            
        except requests.RequestException as e:
            raise RuntimeError(f"Chyba při načítání nahrávek pro hovor {call_guid}: {e}")
    
    def download_recording(self, recording_id: str, output_path: Path) -> int:
        """
        Stáhne nahrávku do souboru.
        
        Args:
            recording_id: ID nahrávky
            output_path: Cesta k výstupnímu souboru
            
        Returns:
            int: Velikost staženého souboru v bajtech
        """
        try:
            response = self.session.get(f"{self.api_base_url}/recordings/{recording_id}/download", stream=True)
            response.raise_for_status()
            
            total_size = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            return total_size
            
        except requests.RequestException as e:
            raise RuntimeError(f"Chyba při stahování nahrávky {recording_id}: {e}")


class FakeSpinocoClient:
    """Fake Spinoco client pro testy - čte data z fixtures."""
    
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)
        self._call_counter = 0
        self._recording_counter = 0
    
    def list_calls(self, since: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Simuluje načítání hovorů z fixtures."""
        call_file = self.fixtures_dir / "call_task.json"
        if not call_file.exists():
            return
        
        with open(call_file, 'r', encoding='utf-8') as f:
            call_data = json.load(f)
        
        # Simuluj více hovorů pro testy
        for i in range(3):  # 3 testovací hovory
            if limit and i >= limit:
                break
            
            # Uprav ID a timestamp pro každý hovor
            modified_call = call_data.copy()
            modified_call['id'] = f"{call_data['id']}_{i:02d}"
            modified_call['lastUpdate'] = call_data['lastUpdate'] + (i * 1000)
            
            yield modified_call
    
    def list_recordings(self, call_guid: str) -> List[Dict[str, Any]]:
        """Simuluje načítání nahrávek z fixtures."""
        recordings_file = self.fixtures_dir / "recordings.json"
        if not recordings_file.exists():
            return []
        
        with open(recordings_file, 'r', encoding='utf-8') as f:
            recordings = json.load(f)
        
        # Uprav ID nahrávek podle call_guid
        modified_recordings = []
        for i, recording in enumerate(recordings):
            modified_recording = recording.copy()
            modified_recording['id'] = f"{call_guid}_rec_{i+1:02d}"
            modified_recording['date'] = recording['date'] + (i * 1000)
            modified_recordings.append(modified_recording)
        
        return modified_recordings
    
    def download_recording(self, recording_id: str, output_path: Path) -> int:
        """
        Simuluje stahování nahrávky - vytvoří fake OGG soubor.
        
        Pro testování chyb: pokud recording_id obsahuje "fail", vytvoří poškozený soubor.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if "fail" in recording_id.lower():
            # Simuluj poškozený soubor
            with open(output_path, 'wb') as f:
                f.write(b"INVALID_OGG_DATA")
            return 15
        else:
            # Simuluj platný OGG soubor (minimální OGG header)
            fake_ogg_data = b"OggS" + b"\x00" * 23 + b"vorbis" + b"\x00" * 1000
            with open(output_path, 'wb') as f:
                f.write(fake_ogg_data)
            return len(fake_ogg_data)
