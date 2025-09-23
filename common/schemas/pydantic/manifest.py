"""
Pydantic modely pro manifest validaci.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator


class ProducerModel(BaseModel):
    """Model pro producer informace."""
    git_sha: str
    host: str
    user: str
    processor_version: Optional[str] = None


class InputRefModel(BaseModel):
    """Model pro input reference."""
    type: str
    value: str


class OutputsModel(BaseModel):
    """Model pro outputs."""
    primary: str
    aux: Optional[Dict[str, str]] = None


class ErrorModel(BaseModel):
    """Model pro error záznam."""
    unit_id: str
    error_key: str
    message: str = ""


class ManifestModel(BaseModel):
    """Pydantic model pro manifest validaci."""
    
    schema_id: str = Field(..., alias='schema', description="Schema identifier")
    schema_version: str = Field(..., description="Semantic version")
    step_id: str = Field(..., description="Step identifier")
    step_run_id: str = Field(..., description="Step run ID")
    flow_run_id: Optional[str] = Field(None, description="Flow run ID")
    
    producer: ProducerModel = Field(..., description="Producer information")
    
    run_mode: str = Field(..., description="Run mode")
    started_at_utc: str = Field(..., description="Start timestamp")
    finished_at_utc: Optional[str] = Field(None, description="Finish timestamp")
    
    status: str = Field(..., description="Run status")
    
    input_refs: List[InputRefModel] = Field(default_factory=list, description="Input references")
    outputs: OutputsModel = Field(..., description="Output files")
    
    counts: Dict[str, int] = Field(default_factory=dict, description="Count statistics")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Performance metrics")
    
    errors: List[ErrorModel] = Field(default_factory=list, description="Error records")
    notes: Optional[str] = Field(None, description="Optional notes")
    
    @field_validator('schema_version')
    @classmethod
    def validate_schema_version(cls, v):
        """Validuje že schema_version je ve formátu semver."""
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError(f"schema_version musí být ve formátu semver (X.Y.Z): {v}")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validuje že status je platný."""
        valid_statuses = {'success', 'error', 'partial'}
        if v not in valid_statuses:
            raise ValueError(f"status musí být jeden z {valid_statuses}: {v}")
        return v
    
    @field_validator('run_mode')
    @classmethod
    def validate_run_mode(cls, v):
        """Validuje že run_mode je platný."""
        valid_modes = {'backfill', 'incr', 'dry'}
        if v not in valid_modes:
            raise ValueError(f"run_mode musí být jeden z {valid_modes}: {v}")
        return v
    
    @field_validator('started_at_utc')
    @classmethod
    def validate_started_at_utc(cls, v):
        """Validuje že started_at_utc je platný ISO timestamp."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"started_at_utc musí být platný ISO timestamp: {v}")
        return v
    
    @field_validator('finished_at_utc')
    @classmethod
    def validate_finished_at_utc(cls, v):
        """Validuje že finished_at_utc je platný ISO timestamp."""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"finished_at_utc musí být platný ISO timestamp: {v}")
        return v
    
    @field_validator('outputs')
    @classmethod
    def validate_outputs(cls, v):
        """Validuje že outputs má povinné primary."""
        if not v.primary:
            raise ValueError("outputs.primary je povinné")
        return v
    
    @field_validator('errors')
    @classmethod
    def validate_errors_status_consistency(cls, v, info):
        """Validuje konzistenci mezi status a errors."""
        status = info.data.get('status')
        if status == 'success' and v:
            raise ValueError("status='success' nesmí mít errors")
        if status in {'error', 'partial'} and not v:
            raise ValueError(f"status='{status}' musí mít alespoň jeden error")
        return v


def validate_manifest_dict(d: Dict[str, Any]) -> ManifestModel:
    """
    Validuje manifest dict a vrátí ManifestModel.
    
    Args:
        d: Dictionary s manifest daty
        
    Returns:
        ManifestModel: Validovaný model
        
    Raises:
        ValueError: Pokud validace selže
    """
    try:
        return ManifestModel(**d)
    except Exception as e:
        raise ValueError(f"Manifest validace selhala: {e}")


def validate_manifest_file(path: Union[str, 'Path']) -> ManifestModel:
    """
    Validuje manifest soubor a vrátí ManifestModel.
    
    Args:
        path: Cesta k manifest souboru
        
    Returns:
        ManifestModel: Validovaný model
        
    Raises:
        ValueError: Pokud validace selže
    """
    import json
    from pathlib import Path
    
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
    
    return validate_manifest_dict(data)
