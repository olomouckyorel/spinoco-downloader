"""
Adapter pro mapování existujícího Whisper JSON výstupu na náš standardizovaný formát.
"""

import hashlib
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


def normalize_recording(transcript_json: Dict[str, Any], recording_id: str, call_id: str, audio_rel_path: str) -> Dict[str, Any]:
    """
    Normalizuje Whisper JSON výstup do našeho standardizovaného formátu.
    
    Args:
        transcript_json: Whisper JSON výstup
        recording_id: ID nahrávky (např. "20240822_054336_71da9579_p01")
        call_id: ID hovoru (např. "20240822_054336_71da9579")
        audio_rel_path: Relativní cesta k audio souboru
        
    Returns:
        Dict: Normalizovaný recording-level transcript
    """
    
    # Extrahuj základní data
    transcription = transcript_json.get('transcription', {})
    metadata = transcript_json.get('metadata', {})
    
    # Zpracuj segmenty
    segments = []
    for segment in transcription.get('segments', []):
        normalized_segment = {
            'start': segment.get('start', 0.0),
            'end': segment.get('end', 0.0),
            'text': segment.get('text', '').strip()
        }
        segments.append(normalized_segment)
    
    # Spoj text ze segmentů
    text = transcription.get('text', '').strip()
    if not text and segments:
        text = ' '.join(seg['text'] for seg in segments)
    
    # Vypočti metriky
    seg_count = len(segments)
    avg_seg_len_s = 0.0
    if seg_count > 0:
        total_duration = sum(seg['end'] - seg['start'] for seg in segments)
        avg_seg_len_s = total_duration / seg_count
    
    # Sestav ASR metadata
    asr_settings = {
        'model': metadata.get('whisper_model', 'unknown'),
        'device': metadata.get('device_used', 'unknown'),
        'beam_size': metadata.get('beam_size'),
        'best_of': metadata.get('best_of'),
        'temperature': metadata.get('temperature'),
        'language': metadata.get('language', 'cs'),
        'initial_prompt': metadata.get('initial_prompt')
    }
    
    # Vyčisti None hodnoty
    asr_settings = {k: v for k, v in asr_settings.items() if v is not None}
    
    # Vytvoř hash z ASR settings pro idempotenci
    asr_settings_str = json.dumps(asr_settings, sort_keys=True)
    asr_settings_hash = hashlib.md5(asr_settings_str.encode()).hexdigest()
    
    # Vytvoř hash z textu pro detekci změn
    transcript_hash = hashlib.md5(text.encode()).hexdigest()
    
    # Sestav výsledný dokument
    result = {
        'call_id': call_id,
        'recording_id': recording_id,
        'duration_s': metadata.get('duration'),
        'lang': metadata.get('language', 'cs'),
        'asr': {
            'provider': 'existing',
            'model': metadata.get('whisper_model', 'unknown'),
            'device': metadata.get('device_used', 'unknown'),
            'settings': asr_settings
        },
        'segments': segments,
        'text': text,
        'metrics': {
            'seg_count': seg_count,
            'avg_seg_len_s': round(avg_seg_len_s, 2)
        },
        'source': {
            'audio_path': audio_rel_path,
            'transcript_source': 'existing-json'
        },
        'processing': {
            'asr_settings_hash': asr_settings_hash,
            'transcript_hash': transcript_hash,
            'processed_at_utc': metadata.get('processed_at', 'unknown')
        }
    }
    
    return result


def normalize_call_level(recording_transcripts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agreguje recording-level transkripty do call-level dokumentu.
    
    Args:
        recording_transcripts: Seznam normalizovaných recording-level transkriptů
        
    Returns:
        Dict: Call-level agregovaný transkript
    """
    
    if not recording_transcripts:
        return {}
    
    # Seřaď podle recording_id (deterministické pořadí)
    sorted_recordings = sorted(recording_transcripts, key=lambda x: x['recording_id'])
    
    # Extrahuj call_id (mělo by být stejné pro všechny)
    call_id = sorted_recordings[0]['call_id']
    
    # Agreguj segmenty s recording_id
    all_segments = []
    for recording in sorted_recordings:
        recording_id = recording['recording_id']
        for segment in recording.get('segments', []):
            segment_with_recording = segment.copy()
            segment_with_recording['recording_id'] = recording_id
            all_segments.append(segment_with_recording)
    
    # Agreguj text s oddělovači
    text_parts = []
    for recording in sorted_recordings:
        recording_id = recording['recording_id']
        text = recording.get('text', '').strip()
        if text:
            text_parts.append(f"[--- {recording_id} ---]\n\n{text}")
    
    aggregated_text = "\n\n".join(text_parts)
    
    # Vypočti metriky
    total_duration = sum(r.get('duration_s', 0) or 0 for r in sorted_recordings)
    total_segments = sum(r.get('metrics', {}).get('seg_count', 0) for r in sorted_recordings)
    avg_seg_len_s = 0.0
    if total_segments > 0:
        total_seg_duration = sum(
            sum(seg['end'] - seg['start'] for seg in r.get('segments', []))
            for r in sorted_recordings
        )
        avg_seg_len_s = total_seg_duration / total_segments
    
    # Agreguj ASR metadata (vezmi z prvního záznamu)
    first_recording = sorted_recordings[0]
    
    result = {
        'call_id': call_id,
        'duration_s': total_duration,
        'lang': first_recording.get('lang', 'cs'),
        'asr': first_recording.get('asr', {}),
        'segments': all_segments,
        'text': aggregated_text,
        'metrics': {
            'recording_count': len(sorted_recordings),
            'total_segments': total_segments,
            'avg_seg_len_s': round(avg_seg_len_s, 2)
        },
        'source': {
            'recording_ids': [r['recording_id'] for r in sorted_recordings],
            'transcript_source': 'existing-json-aggregated'
        },
        'processing': {
            'asr_settings_hash': first_recording.get('processing', {}).get('asr_settings_hash'),
            'transcript_hash': hashlib.md5(aggregated_text.encode()).hexdigest(),
            'processed_at_utc': first_recording.get('processing', {}).get('processed_at_utc')
        }
    }
    
    return result


def load_transcript_json(file_path: Path) -> Dict[str, Any]:
    """
    Načte transcript JSON soubor.
    
    Args:
        file_path: Cesta k JSON souboru
        
    Returns:
        Dict: Načtený JSON
        
    Raises:
        ValueError: Pokud soubor neexistuje nebo není platný JSON
    """
    if not file_path.exists():
        raise ValueError(f"Transcript soubor neexistuje: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Transcript soubor není platný JSON: {e}")
    except Exception as e:
        raise ValueError(f"Chyba při čtení transcript souboru: {e}")


def find_transcript_file(base_path: Path, recording_id: str, outputs_glob: str) -> Optional[Path]:
    """
    Najde transcript soubor pro daný recording_id.
    
    Args:
        base_path: Základní cesta pro hledání
        recording_id: ID nahrávky
        outputs_glob: Glob pattern pro hledání souborů
        
    Returns:
        Optional[Path]: Cesta k nalezenému souboru nebo None
    """
    import glob
    
    # Zkus najít soubor obsahující recording_id v názvu
    patterns = [
        f"**/*{recording_id}*",
        f"**/*{recording_id}*.json",
        outputs_glob
    ]
    
    for pattern in patterns:
        search_path = base_path / pattern
        matches = list(Path(base_path).glob(pattern))
        
        # Prioritizuj soubory obsahující recording_id
        for match in matches:
            if recording_id in match.name:
                return match
        
        # Pokud nic nenajdeš, vezmi první match
        if matches:
            return matches[0]
    
    return None
