"""
Metadata adaptéry pro Spinoco API objekty.

Převádí Spinoco CallTask a CallRecording objekty na naše interní metadata
s UTC časovými razítky a stabilními ID (call_id, recording_id).
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Iterable, Tuple, Optional
from .ids import call_id_from_spinoco, make_recording_ids


def utc_iso_from_ms(ms: int) -> str:
    """
    Převádí UTC epoch timestamp v milisekundách na ISO string.
    
    Args:
        ms: UTC epoch timestamp v milisekundách
        
    Returns:
        str: ISO timestamp ve formátu '2024-08-22T05:43:36Z'
        
    Example:
        utc_iso_from_ms(1724305416000) -> '2024-08-22T05:43:36Z'
    """
    if ms < 0:
        raise ValueError(f"Timestamp musí být nezáporné: {ms}")
    
    utc_dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def normalize_call_task(call_task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizuje CallTask objekt na naše interní metadata.
    
    Args:
        call_task: Spinoco CallTask dict s klíči 'id', 'lastUpdate', ...
        
    Returns:
        dict: Normalizované metadata s našimi ID a UTC časovými razítky
        
    Example:
        Input: {"id": "71da9579-7730-11ee-9300-a3a8e273fd52", "lastUpdate": 1724305416000, ...}
        Output: {
            "call_id": "20240822_054336_71da9579",
            "spinoco_call_guid": "71da9579-7730-11ee-9300-a3a8e273fd52",
            "last_update_ms": 1724305416000,
            "call_ts_utc": "2024-08-22T05:43:36Z",
            "raw": {...}  # původní pole pro audit
        }
    """
    if not call_task or 'id' not in call_task or 'lastUpdate' not in call_task:
        raise ValueError("CallTask musí obsahovat 'id' a 'lastUpdate'")
    
    call_guid = call_task['id']
    last_update_ms = call_task['lastUpdate']
    
    # Generuj naše call_id
    call_id = call_id_from_spinoco(last_update_ms, call_guid)
    
    # Převod na UTC ISO
    call_ts_utc = utc_iso_from_ms(last_update_ms)
    
    return {
        'call_id': call_id,
        'spinoco_call_guid': call_guid,
        'last_update_ms': last_update_ms,
        'call_ts_utc': call_ts_utc,
        'raw': call_task  # Původní data pro audit
    }


def build_recordings_metadata(call_doc: Dict[str, Any], recordings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Vytvoří metadata pro nahrávky s deterministickým číslováním.
    
    Nahrávky se seřadí podle (date asc, id lexicograficky) a očíslují _p01, _p02, ...
    Nahrávky bez date se vynechají.
    
    Args:
        call_doc: Normalizované call metadata (obsahuje call_id)
        recordings: Iterable CallRecording objektů
        
    Returns:
        List[Dict]: Seznam normalizovaných recording metadat
        
    Example:
        call_doc = {"call_id": "20240822_054336_71da9579", ...}
        recordings = [
            {"id": "rec1", "date": 1724305416000, "duration": 120, "available": True},
            {"id": "rec2", "date": 1724305417000, "duration": 90, "available": False}
        ]
        # Vrátí seřazené podle date s _p01, _p02
    """
    if 'call_id' not in call_doc:
        raise ValueError("call_doc musí obsahovat 'call_id'")
    
    call_id = call_doc['call_id']
    call_guid = call_doc.get('spinoco_call_guid', '')
    
    # Filtruj nahrávky s validním date
    valid_recordings = []
    for recording in recordings:
        if recording.get('date') is not None and recording['date'] >= 0:
            valid_recordings.append(recording)
    
    if not valid_recordings:
        return []
    
    # Seřaď podle (date, id) pro deterministické číslování
    sorted_recordings = sorted(valid_recordings, key=lambda r: (r['date'], r['id']))
    
    # Generuj recording_ids
    recording_mapping = make_recording_ids(call_id, sorted_recordings)
    
    # Vytvoř metadata pro každou nahrávku
    result = []
    for recording in sorted_recordings:
        recording_id = recording_mapping[recording['id']]
        recording_date_ms = recording['date']
        
        result.append({
            'spinoco_recording_id': recording['id'],
            'spinoco_call_guid': call_guid,
            'recording_id': recording_id,
            'recording_date_ms': recording_date_ms,
            'recording_ts_utc': utc_iso_from_ms(recording_date_ms),
            'duration_s': recording.get('duration'),
            'available': recording.get('available')
        })
    
    return result


def spinoco_to_internal(call_task: Dict[str, Any], recordings: Iterable[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Convenience wrapper - převádí Spinoco objekty na naše interní metadata.
    
    Args:
        call_task: Spinoco CallTask dict
        recordings: Iterable CallRecording objektů
        
    Returns:
        Tuple[Dict, List[Dict]]: (call_metadata, recordings_metadata)
        
    Example:
        call_task = {"id": "71da9579-...", "lastUpdate": 1724305416000, ...}
        recordings = [{"id": "rec1", "date": 1724305416000, ...}, ...]
        
        call_meta, recordings_meta = spinoco_to_internal(call_task, recordings)
        # call_meta: {"call_id": "20240822_054336_71da9579", ...}
        # recordings_meta: [{"recording_id": "20240822_054336_71da9579_p01", ...}, ...]
    """
    # Normalizuj call task
    call_metadata = normalize_call_task(call_task)
    
    # Vytvoř recordings metadata
    recordings_metadata = build_recordings_metadata(call_metadata, recordings)
    
    return call_metadata, recordings_metadata


def validate_call_task(call_task: Dict[str, Any]) -> bool:
    """
    Validuje že CallTask má požadovaná pole.
    
    Args:
        call_task: CallTask dict k validaci
        
    Returns:
        bool: True pokud je validní
    """
    if not isinstance(call_task, dict):
        return False
    
    required_fields = ['id', 'lastUpdate']
    return all(field in call_task for field in required_fields)


def validate_recording(recording: Dict[str, Any]) -> bool:
    """
    Validuje že CallRecording má požadovaná pole.
    
    Args:
        recording: CallRecording dict k validaci
        
    Returns:
        bool: True pokud je validní
    """
    if not isinstance(recording, dict):
        return False
    
    required_fields = ['id']
    return all(field in recording for field in required_fields)
