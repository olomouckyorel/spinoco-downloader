"""
Anonymizer pro redigování PII z transkriptů.

Obsahuje regex-based detekci a nahrazování PII s deterministickým tagováním.
"""

import re
import hashlib
import json
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path


class PIIAnonymizer:
    """Anonymizer pro detekci a nahrazování PII."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tags_prefix = config.get('tags_prefix', '@')
        
        # Kompiluj regex patterny
        self.patterns = {}
        if config.get('redact_phone', True):
            self.patterns['PHONE'] = re.compile(
                r'(\+?420[\s-]?)?(\d[\s-]?){9,11}',
                re.IGNORECASE
            )
        
        if config.get('redact_email', True):
            self.patterns['EMAIL'] = re.compile(
                r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
                re.IGNORECASE
            )
        
        if config.get('redact_iban', True):
            self.patterns['IBAN'] = re.compile(
                r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b',
                re.IGNORECASE
            )
        
        if config.get('redact_address', False):
            # Základní adresy - později rozšíříme o NER
            self.patterns['ADDRESS'] = re.compile(
                r'\b\d+\s+[A-Za-záčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\s]+(?:ulice|třída|náměstí|nábřeží)\b',
                re.IGNORECASE
            )
    
    def redact_text(self, text: str, context: Optional[Dict[str, Dict[str, str]]] = None) -> Tuple[str, Dict[str, int]]:
        """
        Rediguje PII v textu s deterministickým tagováním.
        
        Args:
            text: Text k redigování
            context: Kontext s již přiřazenými tagy (volitelné)
            
        Returns:
            Tuple[str, Dict]: (redigovaný text, počty náhrad)
        """
        if context is None:
            context = {}
        
        redacted_text = text
        counts = {}
        
        for pii_type, pattern in self.patterns.items():
            if pii_type not in context:
                context[pii_type] = {}
            
            count = 0
            
            def replace_match(match):
                nonlocal count
                original = match.group(0)
                
                # Zkontroluj jestli už máme tag pro tuto hodnotu
                for tag, value in context[pii_type].items():
                    if value == original:
                        return tag
                
                # Vytvoř nový tag
                count += 1
                tag = f"{self.tags_prefix}{pii_type}_{count}"
                context[pii_type][tag] = original
                return tag
            
            redacted_text = pattern.sub(replace_match, redacted_text)
            counts[pii_type] = count
        
        return redacted_text, counts
    
    def create_vault_map(self, context: Dict[str, Dict[str, str]], salt: str = "default_salt") -> Dict[str, str]:
        """
        Vytvoří vault map s salted hash hodnotami.
        
        Args:
            context: Kontext s PII hodnotami
            salt: Salt pro hashování
            
        Returns:
            Dict: Mapování tag → salted hash
        """
        vault_map = {}
        
        for pii_type, values in context.items():
            for tag, original_value in values.items():
                # Vytvoř salted hash
                salted_value = f"{salt}:{original_value}"
                hash_value = hashlib.sha256(salted_value.encode('utf-8')).hexdigest()
                vault_map[tag] = hash_value
        
        return vault_map


def redact_recording(recording: Dict[str, Any], config: Dict[str, Any], context: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Rediguje recording-level transkript.
    
    Args:
        recording: Recording-level transkript
        config: Konfigurace anonymizace
        context: Kontext s PII tagy
        
    Returns:
        Dict: Redigovaný recording s PII stats
    """
    anonymizer = PIIAnonymizer(config)
    
    # Vytvoř kopii záznamu
    redacted_recording = recording.copy()
    
    # Rediguj hlavní text
    redacted_text, text_counts = anonymizer.redact_text(recording['text'], context)
    redacted_recording['text'] = redacted_text
    
    # Rediguj segmenty
    redacted_segments = []
    total_counts = {}
    
    for segment in recording.get('segments', []):
        redacted_segment = segment.copy()
        redacted_segment_text, segment_counts = anonymizer.redact_text(segment['text'], context)
        redacted_segment['text'] = redacted_segment_text
        redacted_segments.append(redacted_segment)
        
        # Agreguj počty
        for pii_type, count in segment_counts.items():
            total_counts[pii_type] = total_counts.get(pii_type, 0) + count
    
    redacted_recording['segments'] = redacted_segments
    
    # Přidej PII stats
    redacted_recording['pii_stats'] = {
        'total_replacements': sum(total_counts.values()),
        'by_type': total_counts
    }
    
    return redacted_recording


def redact_call(call: Dict[str, Any], config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Rediguje call-level transkript.
    
    Args:
        call: Call-level transkript
        config: Konfigurace anonymizace
        
    Returns:
        Tuple[Dict, Dict]: (redigovaný call, vault map)
    """
    anonymizer = PIIAnonymizer(config)
    context = {}
    
    # Vytvoř kopii záznamu
    redacted_call = call.copy()
    
    # Rediguj hlavní text
    redacted_text, text_counts = anonymizer.redact_text(call['text'], context)
    redacted_call['text'] = redacted_text
    
    # Rediguj segmenty
    redacted_segments = []
    total_counts = {}
    
    for segment in call.get('segments', []):
        redacted_segment = segment.copy()
        redacted_segment_text, segment_counts = anonymizer.redact_text(segment['text'], context)
        redacted_segment['text'] = redacted_segment_text
        redacted_segments.append(redacted_segment)
        
        # Agreguj počty
        for pii_type, count in segment_counts.items():
            total_counts[pii_type] = total_counts.get(pii_type, 0) + count
    
    redacted_call['segments'] = redacted_segments
    
    # Přidej PII stats
    redacted_call['pii_stats'] = {
        'total_replacements': sum(total_counts.values()),
        'by_type': total_counts
    }
    
    # Vytvoř vault map
    vault_map = anonymizer.create_vault_map(context)
    
    return redacted_call, vault_map


def load_transcript_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Načte transcript JSONL soubor.
    
    Args:
        file_path: Cesta k JSONL souboru
        
    Returns:
        List[Dict]: Seznam transkriptů
        
    Raises:
        ValueError: Pokud soubor neexistuje nebo není platný JSONL
    """
    if not file_path.exists():
        raise ValueError(f"Transcript soubor neexistuje: {file_path}")
    
    transcripts = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        transcript = json.loads(line)
                        transcripts.append(transcript)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Neplatný JSON na řádku {line_num}: {e}")
    except Exception as e:
        raise ValueError(f"Chyba při čtení transcript souboru: {e}")
    
    return transcripts


def save_transcript_file(transcripts: List[Dict[str, Any]], file_path: Path) -> None:
    """
    Uloží transkripty do JSONL souboru.
    
    Args:
        transcripts: Seznam transkriptů
        file_path: Cesta k výstupnímu souboru
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        for transcript in transcripts:
            json.dump(transcript, f, ensure_ascii=False)
            f.write('\n')


def save_vault_map(vault_map: Dict[str, str], file_path: Path) -> None:
    """
    Uloží vault map do JSON souboru.
    
    Args:
        vault_map: Mapování tag → salted hash
        file_path: Cesta k výstupnímu souboru
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(vault_map, f, indent=2, ensure_ascii=False)


def get_call_recordings(recordings: List[Dict[str, Any]], call_id: str) -> List[Dict[str, Any]]:
    """
    Vrátí všechny recordingy pro daný call_id.
    
    Args:
        recordings: Seznam všech recordingů
        call_id: ID hovoru
        
    Returns:
        List[Dict]: Recordingy pro daný call
    """
    return [rec for rec in recordings if rec.get('call_id') == call_id]


def aggregate_pii_stats(recordings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agreguje PII statistiky z recordingů.
    
    Args:
        recordings: Seznam recordingů s PII stats
        
    Returns:
        Dict: Agregované statistiky
    """
    total_replacements = 0
    by_type = {}
    
    for recording in recordings:
        pii_stats = recording.get('pii_stats', {})
        total_replacements += pii_stats.get('total_replacements', 0)
        
        for pii_type, count in pii_stats.get('by_type', {}).items():
            by_type[pii_type] = by_type.get(pii_type, 0) + count
    
    return {
        'total_replacements': total_replacements,
        'by_type': by_type,
        'recording_count': len(recordings)
    }
