"""
Spinoco API client pro steps/01_ingest_spinoco.

Obsahuje jak reálný SpinocoClient tak FakeSpinocoClient pro testy.
"""

import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime, timezone
import httpx

# Import původního SpinocoClient
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from src.spinoco_client import SpinocoClient as OriginalSpinocoClient


class SpinocoClient:
    """Použije původní SpinocoClient přímo."""
    
    def __init__(self, api_base_url: str, token: str, page_size: int = 100):
        self.api_base_url = api_base_url.rstrip('/')
        self.token = token
        self.page_size = page_size
        
        # Použijeme původní SpinocoClient přímo
        self.client = OriginalSpinocoClient(
            api_token=token,
            base_url=api_base_url
        )
    
    def list_calls(self, since: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """
        Načte seznam hovorů pomocí původního SpinocoClient (sync wrapper).
        
        Args:
            since: ISO timestamp pro filtrování (volitelné)
            limit: Maximální počet hovorů (volitelné)
            
        Yields:
            Dict: CallTask data
        """
        import asyncio
        
        async def _async_list_calls():
            count = 0
            
            async for call_task in self.original_client.get_completed_calls_with_recordings():
                if limit and count >= limit:
                    break
                    
                # Konvertuj CallTask na dict
                task_dict = {
                    'id': call_task.id,
                    'lastUpdate': call_task.lastUpdate,
                    'tpe': call_task.tpe,
                    'result': call_task.result,
                    'detail': call_task.detail,
                    'hashTags': call_task.hashTags,
                    'owner': call_task.owner,
                    'assignee': call_task.assignee
                }
                
                # Debug: vypiš první task
                if count == 0:
                    print(f"První task: {task_dict.get('id')}, detail: {task_dict.get('detail', {}).get('__tpe')}")
                
                # Filtruj podle 'since' pokud je zadáno
                if since:
                    from datetime import datetime
                    since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                    since_ms = int(since_dt.timestamp() * 1000)
                    if task_dict.get('lastUpdate', 0) < since_ms:
                        continue
                
                yield task_dict
                count += 1
        
        # Spusť async funkci a vrať výsledky
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            async_gen = _async_list_calls()
            while True:
                try:
                    task_dict = loop.run_until_complete(async_gen.__anext__())
                    yield task_dict
                except StopAsyncIteration:
                    break
        finally:
            if loop.is_running():
                loop.close()
    
    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        """
        Načte detail informace pro konkrétní task podle dokumentace.
        
        Args:
            task_id: ID tasku
            
        Returns:
            Dict: Detail informace tasku
        """
        try:
            response = self.client.get(f"{self.api_base_url}/task/{task_id}")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise RuntimeError(f"Chyba při načítání detailu tasku {task_id}: {e}")
    
    def list_recordings(self, call_task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrahuje nahrávky z CallTask objektu pomocí původního clientu.
        
        Args:
            call_task: CallTask data ze Spinoco API
            
        Returns:
            List[Dict]: Seznam nahrávek
        """
        # Konvertuj dict zpět na CallTask objekt
        from src.spinoco_client import CallTask
        task_obj = CallTask(**call_task)
        
        # Použij původní metodu
        recordings = self.original_client.extract_available_recordings(task_obj)
        
        # Konvertuj zpět na dict
        return [recording.dict() for recording in recordings]
    
    def download_recording(self, recording_id: str, output_path: Path) -> int:
        """
        Stáhne nahrávku do souboru pomocí původního clientu (sync wrapper).
        
        Args:
            recording_id: ID nahrávky
            output_path: Cesta k výstupnímu souboru
            
        Returns:
            int: Velikost staženého souboru v bajtech
        """
        import asyncio
        
        async def _async_download():
            audio_data = await self.original_client.download_recording(recording_id)
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return len(audio_data)
        
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            try:
                return loop.run_until_complete(_async_download())
            finally:
                if loop.is_running():
                    loop.close()
        except Exception as e:
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
