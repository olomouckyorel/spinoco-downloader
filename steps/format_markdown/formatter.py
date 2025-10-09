"""
Formatter pro převod JSONL transkriptů do čitelných Markdown souborů.
"""

from datetime import timedelta
from typing import Dict, Any, List
from pathlib import Path


def format_time(seconds: float) -> str:
    """Formátuje sekundy do HH:MM:SS formátu."""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    secs = int(td.total_seconds() % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_call_to_markdown(call: Dict[str, Any], include_metadata: bool = True) -> str:
    """
    Převede call-level transcript do Markdown formátu.
    
    Args:
        call: Call dictionary z transcripts_calls_redacted.jsonl
        include_metadata: Zda zahrnout metadata sekci
        
    Returns:
        Markdown string
    """
    lines = []
    
    # Header
    call_id = call.get('call_id', 'unknown')
    lines.append(f"# Hovor {call_id}")
    lines.append("")
    
    # Metadata
    if include_metadata:
        lines.append("## 📊 Metadata")
        lines.append("")
        
        duration_s = call.get('duration_s')
        if duration_s:
            duration_str = format_time(duration_s)
            lines.append(f"- **Délka:** {duration_str}")
        
        lang = call.get('lang', 'unknown')
        lines.append(f"- **Jazyk:** {lang}")
        
        asr = call.get('asr', {})
        model = asr.get('model', 'unknown')
        lines.append(f"- **Model:** {model}")
        
        # PII stats
        pii_stats = call.get('pii_stats', {})
        total_replacements = pii_stats.get('total_replacements', 0)
        if total_replacements > 0:
            by_type = pii_stats.get('by_type', {})
            lines.append(f"- **PII nahrazeno:** {total_replacements}")
            for pii_type, count in by_type.items():
                if count > 0:
                    lines.append(f"  - {pii_type}: {count}x")
        else:
            lines.append(f"- **PII nahrazeno:** 0 (žádné citlivé údaje)")
        
        # Metrics
        metrics = call.get('metrics', {})
        seg_count = metrics.get('recording_count') or metrics.get('total_segments', 0)
        if seg_count:
            lines.append(f"- **Segmentů:** {seg_count}")
        
        lines.append("")
    
    # Transcript
    lines.append("## 📝 Přepis")
    lines.append("")
    
    segments = call.get('segments', [])
    
    if segments:
        for idx, segment in enumerate(segments):
            start = segment.get('start', 0.0)
            text = segment.get('text', '').strip()
            speaker_id = segment.get('speaker', 'unknown')
            
            if text:
                # Mapování speaker ID na label
                if speaker_id == 'customer':
                    speaker = "🙋 **Zákazník:**"
                elif speaker_id == 'technician':
                    speaker = "👨‍🔧 **Technik:**"
                else:
                    # Fallback: alternování podle pořadí
                    speaker = "🙋 **Zákazník:**" if idx % 2 == 0 else "👨‍🔧 **Technik:**"
                
                time_str = format_time(start)
                lines.append(f"**[{time_str}]** {speaker} {text}")
                lines.append("")
    else:
        # Fallback - použij celý text
        text = call.get('text', '')
        if text:
            lines.append(text)
            lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Vygenerováno z anonymizovaného transkriptu*")
    
    return '\n'.join(lines)


def format_recording_to_markdown(recording: Dict[str, Any], include_metadata: bool = True) -> str:
    """
    Převede recording-level transcript do Markdown formátu.
    
    Args:
        recording: Recording dictionary z transcripts_recordings_redacted.jsonl
        include_metadata: Zda zahrnout metadata sekci
        
    Returns:
        Markdown string
    """
    lines = []
    
    # Header
    recording_id = recording.get('recording_id', 'unknown')
    call_id = recording.get('call_id', 'unknown')
    lines.append(f"# Nahrávka {recording_id}")
    lines.append("")
    lines.append(f"*Part of call: {call_id}*")
    lines.append("")
    
    # Metadata
    if include_metadata:
        lines.append("## 📊 Metadata")
        lines.append("")
        
        duration_s = recording.get('duration_s')
        if duration_s:
            duration_str = format_time(duration_s)
            lines.append(f"- **Délka:** {duration_str}")
        
        lang = recording.get('lang', 'unknown')
        lines.append(f"- **Jazyk:** {lang}")
        
        asr = recording.get('asr', {})
        model = asr.get('model', 'unknown')
        lines.append(f"- **Model:** {model}")
        
        # PII stats
        pii_stats = recording.get('pii_stats', {})
        total_replacements = pii_stats.get('total_replacements', 0)
        if total_replacements > 0:
            by_type = pii_stats.get('by_type', {})
            lines.append(f"- **PII nahrazeno:** {total_replacements}")
            for pii_type, count in by_type.items():
                if count > 0:
                    lines.append(f"  - {pii_type}: {count}x")
        else:
            lines.append(f"- **PII nahrazeno:** 0")
        
        lines.append("")
    
    # Transcript
    lines.append("## 📝 Přepis")
    lines.append("")
    
    segments = recording.get('segments', [])
    
    if segments:
        for segment in segments:
            start = segment.get('start', 0.0)
            text = segment.get('text', '').strip()
            
            if text:
                time_str = format_time(start)
                lines.append(f"**[{time_str}]** {text}")
                lines.append("")
    else:
        # Fallback
        text = recording.get('text', '')
        if text:
            lines.append(text)
            lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Anonymizovaný přepis - Recording ID: {recording_id}*")
    
    return '\n'.join(lines)


def save_markdown(markdown_text: str, output_path: Path) -> None:
    """Uloží Markdown do souboru."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
