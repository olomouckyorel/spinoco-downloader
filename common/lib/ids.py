"""
ID generátory pro Spinoco pipeline.

Poskytuje stabilní identifikátory:
- call_id: UTC timestamp + first8(call_guid)
- recording_id: call_id + _pNN (deterministic numbering)
- run_id: ULID (time-sortable)
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Any
import ulid


def new_ulid() -> str:
    """
    Generuje nový ULID (time-sortable, lexicographically sortable).
    
    Returns:
        str: 26-znakový ULID v Crockford Base32 formátu
    """
    return str(ulid.new())


def new_run_id() -> str:
    """
    Alias pro new_ulid() - generuje run ID pro pipeline běhy.
    
    Returns:
        str: ULID string pro identifikaci běhu
    """
    return new_ulid()


def call_id_from_spinoco(last_update_ms: int, call_guid: str) -> str:
    """
    Vytvoří call_id z Spinoco dat.
    
    Formát: YYYYMMDD_HHMMSS_first8guid
    
    Args:
        last_update_ms: UTC epoch timestamp v milisekundách
        call_guid: Spinoco call GUID (např. "71da9579-7730-11ee-9300-a3a8e273fd52")
        
    Returns:
        str: call_id ve formátu "20240822_063016_71da9579"
        
    Raises:
        ValueError: Pokud jsou vstupy nevalidní
    """
    if not call_guid or len(call_guid) < 8:
        raise ValueError(f"call_guid musí mít alespoň 8 znaků: {call_guid}")
    
    if last_update_ms <= 0:
        raise ValueError(f"last_update_ms musí být kladné: {last_update_ms}")
    
    # Převod UTC ms epoch na YYYYMMDD_HHMMSS
    utc_dt = datetime.fromtimestamp(last_update_ms / 1000, tz=timezone.utc)
    timestamp_str = utc_dt.strftime("%Y%m%d_%H%M%S")
    
    # Prvních 8 znaků z GUID
    guid_prefix = call_guid[:8]
    
    return f"{timestamp_str}_{guid_prefix}"


def make_recording_ids(call_id: str, recordings: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Vrací Spinoco recording ID přímo bez naší nadstavby.
    
    Spinoco má své ID promyšlené, takže je použijeme přímo.
    
    Args:
        call_id: Base call_id (nepoužívá se, zachováno pro kompatibilitu)
        recordings: Lista dictů s klíči 'id' a 'date'
        
    Returns:
        Dict[str, str]: Mapování {recording.id: recording.id} (identity mapping)
        
    Example:
        recordings = [
            {'id': '193c444a-7e91-11f0-a473-2f775d7c125b', 'date': 2},
            {'id': 'ee5e06e7-7f20-11f0-a86e-9de2359f45e9', 'date': 2}
        ]
        # Vrátí: {'193c444a-7e91-11f0-a473-2f775d7c125b': '193c444a-7e91-11f0-a473-2f775d7c125b', 
        #         'ee5e06e7-7f20-11f0-a86e-9de2359f45e9': 'ee5e06e7-7f20-11f0-a86e-9de2359f45e9'}
    """
    if not recordings:
        return {}
    
    # Jednoduché identity mapping - použijeme Spinoco ID přímo
    result = {}
    for recording in recordings:
        spinoco_id = recording.get('id', '')
        if spinoco_id:
            result[spinoco_id] = spinoco_id
    
    return result


def is_valid_call_id(s: str) -> bool:
    """
    Validuje formát call_id.
    
    Očekávaný formát: ^\d{8}_\d{6}_[A-Za-z0-9]{8}$
    
    Args:
        s: String k validaci
        
    Returns:
        bool: True pokud je formát validní
    """
    if not s or not isinstance(s, str):
        return False
    
    pattern = r'^\d{8}_\d{6}_[A-Za-z0-9]{8}$'
    return bool(re.match(pattern, s))


def is_valid_run_id(s: str) -> bool:
    """
    Validuje formát run_id (ULID).
    
    ULID má 26 znaků v Crockford Base32 formátu.
    
    Args:
        s: String k validaci
        
    Returns:
        bool: True pokud je formát validní
    """
    if not s or not isinstance(s, str):
        return False
    
    # ULID má přesně 26 znaků a používá Crockford Base32
    if len(s) != 26:
        return False
    
    # Crockford Base32: 0-9, A-Z (bez I, L, O, U)
    pattern = r'^[0-9A-HJKMNP-TV-Z]{26}$'
    return bool(re.match(pattern, s))


def timestamp_from_call_id(call_id: str) -> datetime:
    """
    Extrahuje timestamp z call_id.
    
    Args:
        call_id: call_id ve formátu "20240822_063016_71da9579"
        
    Returns:
        datetime: UTC datetime objekt
        
    Raises:
        ValueError: Pokud call_id není validní
    """
    if not is_valid_call_id(call_id):
        raise ValueError(f"Nevalidní call_id: {call_id}")
    
    # Extrahovat timestamp část (prvních 15 znaků: YYYYMMDD_HHMMSS)
    timestamp_str = call_id[:15]
    
    # Převést na datetime
    return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")


def extract_call_id_base(call_id: str) -> str:
    """
    Extrahuje base část z call_id (bez timestampu).
    
    Args:
        call_id: call_id ve formátu "20240822_063016_71da9579"
        
    Returns:
        str: Base část (např. "71da9579")
        
    Raises:
        ValueError: Pokud call_id není validní
    """
    if not is_valid_call_id(call_id):
        raise ValueError(f"Nevalidní call_id: {call_id}")
    
    # Base je část za posledním podtržítkem
    return call_id.split('_')[-1]
