"""
Manifest builder pro Spinoco pipeline.

Poskytuje jednoduché API pro vytvoření, plnění a validaci manifest souborů
pro jednotlivé běhy kroků pipeline.
"""

import json
import platform
import getpass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from .ids import new_run_id


class Manifest:
    """
    Builder pro manifest soubory.
    
    Poskytuje fluent API pro vytvoření a plnění manifest dat
    s automatickou validací a finalizací.
    """
    
    def __init__(self):
        """Inicializuje prázdný manifest."""
        self._data: Dict[str, Any] = {}
        self._finalized = False
    
    @classmethod
    def new(cls, *, schema: str, schema_version: str, step_id: str,
            step_run_id: str, flow_run_id: Optional[str] = None, run_mode: str) -> "Manifest":
        """
        Vytvoří nový manifest s povinnými poli.
        
        Args:
            schema: Schema identifier (např. "bh.v1.transcripts")
            schema_version: Semantic version (např. "1.0.0")
            step_id: Step identifier (např. "01_ingest_spinoco")
            step_run_id: Step run ID (ULID)
            flow_run_id: Flow run ID (volitelné)
            run_mode: Run mode ("backfill", "incr", "dry")
            
        Returns:
            Manifest: Nový manifest instance
        """
        manifest = cls()
        
        # Povinná pole
        manifest._data.update({
            'schema': schema,
            'schema_version': schema_version,
            'step_id': step_id,
            'step_run_id': step_run_id,
            'flow_run_id': flow_run_id,
            'run_mode': run_mode,
            'started_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'finished_at_utc': None,
            'status': 'running',  # Dočasný status
            'input_refs': [],
            'outputs': {},
            'counts': {},
            'metrics': {},
            'errors': [],
            'notes': None
        })
        
        # Producer informace
        manifest._data['producer'] = {
            'git_sha': manifest._get_git_sha(),
            'host': platform.node(),
            'user': getpass.getuser(),
            'processor_version': None
        }
        
        return manifest
    
    def add_input_ref(self, ref_type: str, value: str) -> "Manifest":
        """
        Přidá input reference.
        
        Args:
            ref_type: Typ reference (např. "recording_id")
            value: Hodnota reference
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['input_refs'].append({
            'type': ref_type,
            'value': value
        })
        return self
    
    def set_outputs(self, primary: str, **aux: str) -> "Manifest":
        """
        Nastaví output soubory.
        
        Args:
            primary: Primární output soubor (povinný)
            **aux: Pomocné output soubory
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['outputs'] = {
            'primary': primary,
            'aux': aux if aux else None
        }
        return self
    
    def set_counts(self, **counts: int) -> "Manifest":
        """
        Nastaví count statistiky.
        
        Args:
            **counts: Count hodnoty (např. calls=1, recordings=2, errors=0)
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['counts'].update(counts)
        return self
    
    def merge_metrics(self, **metrics: float) -> "Manifest":
        """
        Přidá nebo aktualizuje metriky.
        
        Args:
            **metrics: Metriky (např. avg_asr_conf=0.91, seg_count_mean=42.3)
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['metrics'].update(metrics)
        return self
    
    def add_error(self, unit_id: str, error_key: str, message: str = "") -> "Manifest":
        """
        Přidá error záznam.
        
        Args:
            unit_id: ID jednotky kde došlo k chybě
            error_key: Klíč chyby
            message: Popis chyby
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['errors'].append({
            'unit_id': unit_id,
            'error_key': error_key,
            'message': message
        })
        return self
    
    def set_notes(self, notes: str) -> "Manifest":
        """
        Nastaví poznámky.
        
        Args:
            notes: Poznámky
            
        Returns:
            Manifest: Self pro method chaining
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        self._data['notes'] = notes
        return self
    
    def finalize_success(self) -> "Manifest":
        """
        Finalizuje manifest jako úspěšný.
        
        Returns:
            Manifest: Self pro method chaining
            
        Raises:
            RuntimeError: Pokud manifest má errors
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        if self._data['errors']:
            raise RuntimeError("Úspěšný manifest nesmí mít errors")
        
        self._data['status'] = 'success'
        self._data['finished_at_utc'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self._finalized = True
        return self
    
    def finalize_error(self, partial: bool = False) -> "Manifest":
        """
        Finalizuje manifest jako selhaný.
        
        Args:
            partial: True pro partial success
            
        Returns:
            Manifest: Self pro method chaining
            
        Raises:
            RuntimeError: Pokud manifest nemá errors
        """
        if self._finalized:
            raise RuntimeError("Manifest je již finalizován")
        
        if not self._data['errors']:
            raise RuntimeError("Selhaný manifest musí mít alespoň jeden error")
        
        self._data['status'] = 'partial' if partial else 'error'
        self._data['finished_at_utc'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self._finalized = True
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Vrátí manifest jako dictionary.
        
        Returns:
            Dict: Manifest data
        """
        # Vytvoř kopii s konzistentním pořadím klíčů
        ordered_data = {}
        
        # Povinná pole v pořadí
        for key in ['schema', 'schema_version', 'step_id', 'step_run_id', 'flow_run_id',
                   'producer', 'run_mode', 'started_at_utc', 'finished_at_utc', 'status',
                   'input_refs', 'outputs', 'counts', 'metrics', 'errors', 'notes']:
            if key in self._data:
                ordered_data[key] = self._data[key]
        
        return ordered_data
    
    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "Manifest":
        """
        Načte manifest ze souboru.
        
        Args:
            path: Cesta k manifest souboru
            
        Returns:
            Manifest: Načtený manifest
            
        Raises:
            ValueError: Pokud soubor neexistuje nebo není platný JSON
        """
        path = Path(path)
        if not path.exists():
            raise ValueError(f"Manifest soubor neexistuje: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Manifest soubor není platný JSON: {e}")
        except Exception as e:
            raise ValueError(f"Chyba při čtení manifest souboru: {e}")
        
        manifest = cls()
        manifest._data = data
        manifest._finalized = True  # Načtené manifesty jsou považovány za finalizované
        return manifest
    
    def write(self, path: Union[str, Path]) -> None:
        """
        Zapíše manifest do souboru.
        
        Args:
            path: Cesta k výstupnímu souboru
            
        Raises:
            RuntimeError: Pokud manifest není finalizován
        """
        if not self._finalized:
            raise RuntimeError("Manifest musí být finalizován před zápisem")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def validate(self) -> None:
        """
        Validuje manifest pomocí Pydantic modelu.
        
        Raises:
            ValueError: Pokud validace selže
        """
        from ..schemas.pydantic.manifest import validate_manifest_dict
        
        try:
            validate_manifest_dict(self.to_dict())
        except Exception as e:
            raise ValueError(f"Manifest validace selhala: {e}")
    
    def _get_git_sha(self) -> str:
        """Získá git SHA (zkrácený nebo plný)."""
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Fallback
        return "unknown"


# Convenience funkce
def create_manifest(schema: str, schema_version: str, step_id: str, 
                   run_mode: str = "incr", flow_run_id: Optional[str] = None) -> Manifest:
    """
    Vytvoří nový manifest s automaticky generovaným step_run_id.
    
    Args:
        schema: Schema identifier
        schema_version: Semantic version
        step_id: Step identifier
        run_mode: Run mode
        flow_run_id: Flow run ID (volitelné)
        
    Returns:
        Manifest: Nový manifest
    """
    step_run_id = new_run_id()
    return Manifest.new(
        schema=schema,
        schema_version=schema_version,
        step_id=step_id,
        step_run_id=step_run_id,
        flow_run_id=flow_run_id,
        run_mode=run_mode
    )
