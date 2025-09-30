"""
Spinoco API klient pro stahování hovorů a transkriptů.
Implementuje Call and Chat Transcription and Synchronisation API.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple
from pathlib import Path
import httpx
import structlog
from pydantic import BaseModel, Field

from .config import settings


class TaskQuery(BaseModel):
    """Query parametry pro vyhledávání úkolů."""
    completed: str = "Only"
    queryBy: str = "LastUpdate"
    from_timestamp: Optional[str] = Field(None, alias="from")
    taskQueryTypes: List[str] = ["CallSessionTask"]


class SpinocoTaskRequest(BaseModel):
    """Request pro query úkolů."""
    query: Optional[TaskQuery] = None
    page: Optional[str] = None
    count: int = 50


class CallRecording(BaseModel):
    """Model pro call recording."""
    id: str
    date: Optional[int] = None  # Někdy chybí v API response
    duration: int
    vm: bool
    available: bool
    transcriptions: Dict[str, Any] = {}


class CallTask(BaseModel):
    """Model pro call task."""
    id: str
    lastUpdate: int
    tpe: Dict[str, Any]
    result: Optional[List[Any]] = None
    detail: Optional[Dict[str, Any]] = None
    hashTags: List[Dict[str, Any]] = []
    owner: Dict[str, Any]
    assignee: Dict[str, Any]


class SpinocoResponse(BaseModel):
    """Odpověď ze Spinoco API."""
    next: Optional[str] = None
    result: List[Dict[str, Any]]


class SpinocoClient:
    """
    Klient pro Spinoco Call and Chat Transcription API.
    
    Implementuje synchronizaci hovorů, stahování nahrávek a transkriptů
    podle oficiální dokumentace Spinoco API.
    """
    
    def __init__(self, api_token: str, base_url: str = "https://api.spinoco.com"):
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        self.logger = structlog.get_logger("spinoco_client")
        
        # HTTP klient s timeout a retry logikou
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),  # Zkrátil timeout
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "x-spinoco-protocol-version": "2"
            },
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3)  # Méně spojení
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def get_completed_calls_with_recordings(self) -> AsyncGenerator[CallTask, None]:
        """
        Získá všechny dokončené hovory s nahrávkami podle oficiální API dokumentace.
        
        Implementuje POST /task/query s parametry:
        - completed: "Only" 
        - queryBy: "LastUpdate"
        - taskQueryTypes: ["CallSessionTask"]
        
        Yields:
            CallTask: Hovory s dostupnými nahrávkami
        """
        self.logger.info("Získávám dokončené hovory s nahrávkami")
        
        # Request podle oficiální dokumentace
        # Nastavím from na začátek srpna 2025 (1722470400000 = 2025-08-01T00:00:00Z)
        request_body = {
            "query": {
                "completed": "Only",
                "queryBy": "LastUpdate",
                "from": {"L": "1722470400000"},
                "taskQueryTypes": ["CallSessionTask"]
            },
            "count": 50
        }
        
        page_token = None
        total_calls = 0
        calls_with_recordings = 0
        
        while True:
            if page_token:
                request_body = {
                    "page": page_token,
                    "count": 50
                }
            
            try:
                response = await self._post("/task/query", request_body)
                
                # Zpracuj výsledky
                for task_data in response.get("result", []):
                    try:
                        task = CallTask(**task_data)
                        total_calls += 1
                        
                        # Filtruj jen hovory s nahrávkami
                        if self._has_available_recordings(task):
                            calls_with_recordings += 1
                            yield task
                            
                    except Exception as e:
                        self.logger.warning(
                            "Nepodařilo se parsovat úkol",
                            task_id=task_data.get('id'),
                            error=str(e)
                        )
                
                # Další stránka?
                page_token = response.get("next")
                if not page_token:
                    break
                    
            except Exception as e:
                self.logger.error("Chyba při získávání úkolů", error=str(e))
                raise
        
        self.logger.info(
            f"Synchronizace dokončena: {total_calls} hovorů celkem, "
            f"{calls_with_recordings} s nahrávkami"
        )
    
    def _has_available_recordings(self, task: CallTask) -> bool:
        """Zkontroluje, zda má hovor dostupné nahrávky."""
        detail = task.detail
        if not detail or detail.get("__tpe") != "Recordings":
            return False
        
        recordings = detail.get("recordings", {})
        for recording_data in recordings.values():
            if recording_data.get("available", False):
                return True
        
        return False
    
    def extract_available_recordings(self, task: CallTask) -> List[CallRecording]:
        """Extrahuje dostupné nahrávky z call task."""
        recordings = []
        
        detail = task.detail
        if not detail or detail.get("__tpe") != "Recordings":
            return recordings
        
        recordings_data = detail.get("recordings", {})
        for recording_id, recording_data in recordings_data.items():
            if recording_data.get("available", False):
                try:
                    recording = CallRecording(**recording_data)
                    recordings.append(recording)
                except Exception as e:
                    self.logger.warning(
                        "Nepodařilo se parsovat nahrávku",
                        task_id=task.id,
                        recording_id=recording_id,
                        error=str(e)
                    )
        
        return recordings

    async def get_tasks_since(
        self,
        since_timestamp: Optional[int] = None,
        task_types: List[str] = None,
        batch_size: int = 50
    ) -> AsyncGenerator[CallTask, None]:
        """
        Získá všechny úkoly (hovory/chaty) od zadaného času.
        
        Args:
            since_timestamp: Unix timestamp v ms (None = od začátku)
            task_types: Typy úkolů (default: ["CallSessionTask"])
            batch_size: Velikost stránky
            
        Yields:
            CallTask: Jednotlivé úkoly
        """
        if task_types is None:
            task_types = ["CallSessionTask"]
        
        self.logger.info(
            "Začínám synchronizaci úkolů",
            since_timestamp=since_timestamp,
            task_types=task_types
        )
        
        # Počáteční request
        query = TaskQuery(
            taskQueryTypes=task_types,
            from_timestamp=str(since_timestamp) if since_timestamp else None
        )
        
        request = SpinocoTaskRequest(query=query, count=batch_size)
        page_token = None
        total_tasks = 0
        
        while True:
            if page_token:
                # Další stránka
                request = SpinocoTaskRequest(page=page_token, count=batch_size)
            
            try:
                response = await self._post("/task/query", request.dict(exclude_none=True))
                spinoco_response = SpinocoResponse(**response)
                
                # Zpracuj úkoly z aktuální stránky
                for task_data in spinoco_response.result:
                    try:
                        task = CallTask(**task_data)
                        total_tasks += 1
                        yield task
                    except Exception as e:
                        self.logger.warning(
                            "Nepodařilo se parsovat úkol",
                            task_id=task_data.get('id'),
                            error=str(e)
                        )
                
                # Kontrola další stránky
                if not spinoco_response.next:
                    break
                    
                page_token = spinoco_response.next
                
            except Exception as e:
                self.logger.error("Chyba při získávání úkolů", error=str(e))
                raise
        
        self.logger.info("Synchronizace dokončena", total_tasks=total_tasks)
    
    async def get_call_recordings(self, task: CallTask) -> List[CallRecording]:
        """
        Získá informace o nahrávkách pro daný hovor.
        
        Args:
            task: Call task
            
        Returns:
            List[CallRecording]: Seznam dostupných nahrávek
        """
        recordings = []
        
        if not task.detail or task.detail.get("__tpe") != "Recordings":
            return recordings
        
        recordings_data = task.detail.get("recordings", {})
        
        for recording_id, recording_data in recordings_data.items():
            try:
                recording = CallRecording(**recording_data)
                recordings.append(recording)
            except Exception as e:
                self.logger.warning(
                    "Nepodařilo se parsovat nahrávku",
                    task_id=task.id,
                    recording_id=recording_id,
                    error=str(e)
                )
        
        return recordings
    
    async def download_recording(self, task_id: str, recording_id: str) -> bytes:
        """
        Stáhne nahrávku hovoru v .ogg formátu.
        
        Args:
            task_id: ID úkolu
            recording_id: ID nahrávky
            
        Returns:
            bytes: Binární data nahrávky
        """
        url = f"/recording-direct/{task_id}/{recording_id}"
        
        self.logger.info(
            "Stahuji nahrávku",
            task_id=task_id,
            recording_id=recording_id
        )
        
        try:
            response = await self.client.get(f"{self.base_url}{url}")
            response.raise_for_status()
            
            self.logger.info(
                "Nahrávka stažena",
                task_id=task_id,
                recording_id=recording_id,
                size_bytes=len(response.content)
            )
            
            return response.content
            
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "HTTP chyba při stahování nahrávky",
                task_id=task_id,
                recording_id=recording_id,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise
        except Exception as e:
            self.logger.error(
                "Chyba při stahování nahrávky",
                task_id=task_id,
                recording_id=recording_id,
                error=str(e)
            )
            raise
    
    async def download_transcription(self, task_id: str, recording_id: str) -> Optional[Dict[str, Any]]:
        """
        Stáhne transkript hovoru v JSON formátu.
        
        Args:
            task_id: ID úkolu
            recording_id: ID nahrávky
            
        Returns:
            Dict[str, Any]: JSON data transkriptu nebo None
        """
        url = f"/task/transcription/{task_id}/{recording_id}"
        
        self.logger.info(
            "Stahuji transkript",
            task_id=task_id,
            recording_id=recording_id
        )
        
        try:
            response = await self.client.get(f"{self.base_url}{url}")
            
            if response.status_code == 404:
                self.logger.info(
                    "Transkript není dostupný",
                    task_id=task_id,
                    recording_id=recording_id
                )
                return None
            
            response.raise_for_status()
            transcription_data = response.json()
            
            self.logger.info(
                "Transkript stažen",
                task_id=task_id,
                recording_id=recording_id,
                segments_count=len(transcription_data.get("transcription", []))
            )
            
            return transcription_data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            
            self.logger.error(
                "HTTP chyba při stahování transkriptu",
                task_id=task_id,
                recording_id=recording_id,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise
        except Exception as e:
            self.logger.error(
                "Chyba při stahování transkriptu",
                task_id=task_id,
                recording_id=recording_id,
                error=str(e)
            )
            raise
    
    async def get_skills_labels(self, include_deactivated: bool = False) -> Dict[str, str]:
        """Získá mapování skill ID -> label."""
        url = f"/skill/labels?deactivated={str(include_deactivated).lower()}"
        response = await self._get(url)
        return response
    
    async def get_hashtags_labels(self, include_deactivated: bool = False) -> Dict[str, str]:
        """Získá mapování hashtag ID -> label."""
        url = f"/hashtag/labels?deactivated={str(include_deactivated).lower()}"
        response = await self._get(url)
        return response
    
    async def get_users_names(self, include_deactivated: bool = False) -> Dict[str, str]:
        """Získá mapování user ID -> name."""
        url = f"/user/names?deactivated={str(include_deactivated).lower()}"
        response = await self._get(url)
        return response
    
    async def _get(self, endpoint: str) -> Dict[str, Any]:
        """Provede GET request."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("GET request failed", endpoint=endpoint, error=str(e))
            raise
    
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Provede POST request."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("POST request failed", endpoint=endpoint, error=str(e))
            raise
    
    def get_task_phone_numbers(self, task: CallTask) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrahuje telefonní čísla z úkolu.
        
        Returns:
            Tuple[caller, callee]: Telefonní čísla volajícího a volaného
        """
        try:
            direction = task.tpe.get("direction", {})
            direction_type = direction.get("__tpe")
            
            if direction_type == "Terminating":
                # Příchozí hovor
                caller = direction.get("from", {}).get("number", {}).get("e164")
                callee = direction.get("toPhoneNumber")
            elif direction_type == "Originating":
                # Odchozí hovor
                caller = direction.get("fromPhoneNumber")
                callee = direction.get("to", {}).get("number", {}).get("e164")
            else:
                return None, None
            
            return caller, callee
            
        except Exception as e:
            self.logger.warning(
                "Nepodařilo se extrahovat telefonní čísla",
                task_id=task.id,
                error=str(e)
            )
            return None, None
    
    def format_filename_template(
        self,
        template: str,
        task: CallTask,
        suffix: str = ""
    ) -> str:
        """
        Formátuje template pro název souboru podle Spinoco connector vzoru.
        
        Podporované placeholdery:
        - {{due_date|format}} - datum úkolu s formátováním
        - {{task_id}} - ID úkolu
        - {{call_from}} - číslo volajícího
        - {{call_to}} - číslo volaného
        
        Args:
            template: Template string
            task: Call task
            suffix: Přípona souboru (.ogg, .trans.json, .meta.json)
            
        Returns:
            str: Formátovaný název souboru
        """
        try:
            # Základní náhrada
            result = template
            result = result.replace("{{task_id}}", task.id)
            
            # Telefonní čísla
            caller, callee = self.get_task_phone_numbers(task)
            if caller:
                result = result.replace("{{call_from}}", caller.lstrip('+'))
            if callee:
                result = result.replace("{{call_to}}", callee.lstrip('+'))
            
            # Datum s formátováním
            if "{{due_date" in result:
                # Získej due date z úkolu (v ms)
                due_timestamp = task.lastUpdate  # Použijeme lastUpdate jako fallback
                due_date = datetime.fromtimestamp(due_timestamp / 1000)
                
                # Najdi všechny due_date placeholdery s formátováním
                import re
                pattern = r'\{\{due_date\|([^}]+)\}\}'
                matches = re.findall(pattern, result)
                
                for date_format in matches:
                    # Převod Java formátu na Python formát
                    python_format = self._java_to_python_date_format(date_format)
                    formatted_date = due_date.strftime(python_format)
                    result = result.replace(f"{{{{due_date|{date_format}}}}}", formatted_date)
            
            # Přidej suffix
            if suffix:
                result = f"{result}{suffix}"
            
            return result
            
        except Exception as e:
            self.logger.warning(
                "Chyba při formátování template",
                template=template,
                task_id=task.id,
                error=str(e)
            )
            # Fallback na jednoduché jméno
            return f"{task.id}{suffix}"
    
    def _java_to_python_date_format(self, java_format: str) -> str:
        """Převede Java date formát na Python strftime formát."""
        # Základní mapování Java -> Python
        mappings = {
            'yyyy': '%Y',
            'yy': '%y',
            'MM': '%m',
            'dd': '%d',
            'HH': '%H',
            'mm': '%M',
            'ss': '%S'
        }
        
        result = java_format
        for java_fmt, python_fmt in mappings.items():
            result = result.replace(java_fmt, python_fmt)
        
        return result
