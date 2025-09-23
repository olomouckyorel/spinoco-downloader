# Common Library

Sdílené utility pro Spinoco pipeline.

## ID Formáty

### Call ID
Identifikátor celého hovoru.

**Formát:** `YYYYMMDD_HHMMSS_first8guid`

**Příklad:** `20240822_063016_71da9579`

- `YYYYMMDD_HHMMSS` - UTC timestamp hovoru
- `first8guid` - Prvních 8 znaků z Spinoco Call GUID

### Recording ID  
Identifikátor konkrétní nahrávky (dílu hovoru).

**Formát:** `{call_id}_p{NN}`

**Příklad:** `20240822_063016_71da9579_p01`

- `NN` - Číslování od 01 podle seřazení (date, id)

### Run ID
Identifikátor běhu pipeline.

**Formát:** ULID (26 znaků, Crockford Base32)

**Příklad:** `01J9ZC3AC9V2J9FZK2C3R8K9TQ`

- Časově řaditelný
- Lexikograficky řaditelný

## Použití

```python
from common.lib.ids import (
    call_id_from_spinoco, make_recording_ids, 
    new_run_id, is_valid_call_id
)

# Generuj call_id
call_id = call_id_from_spinoco(1724305416000, "71da9579-7730-11ee-9300-a3a8e273fd52")
# → "20240822_063016_71da9579"

# Generuj recording_ids
recordings = [
    {'id': 'rec1', 'date': 1724305416000},
    {'id': 'rec2', 'date': 1724305417000}
]
recording_ids = make_recording_ids(call_id, recordings)
# → {'rec1': '20240822_063016_71da9579_p01', 'rec2': '20240822_063016_71da9579_p02'}

# Generuj run_id
run_id = new_run_id()
# → "01J9ZC3AC9V2J9FZK2C3R8K9TQ"

# Validuj
assert is_valid_call_id(call_id)
assert is_valid_run_id(run_id)
```

## Proč ULID?

- **Monotonicita** - časově řaditelné
- **Lexikografické řazení** - min/max funguje
- **Kratší než UUID** - 26 vs 36 znaků
- **URL-safe** - Crockford Base32

## Testování

```bash
cd common
pip install -r requirements.txt
pytest tests/test_ids.py -v
```
