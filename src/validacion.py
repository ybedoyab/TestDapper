# Módulo de validación de datos con reglas configurables
import re
from datetime import datetime
from typing import Any, Dict, Tuple

import pandas as pd

try:
    import yaml
except Exception:
    yaml = None


def _load_rules(rules_path: str) -> Dict[str, Dict[str, Any]]:
    if yaml is None:
        raise ImportError("PyYAML no está instalado. Agrega 'PyYAML' a requirements.txt")
    with open(rules_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _is_valid_url(value: str) -> bool:
    pattern = re.compile(r"^(https?://)[\w.-]+(?:\.[\w\.-]+)+[\w\-\._~:/?#\[\]@!$&'()*+,;=.]+$")
    return bool(pattern.match(value))


def _coerce_type(value: Any, t: str) -> Tuple[bool, Any]:
    if value is None:
        return True, None
    if t == 'string':
        try:
            return True, str(value)
        except Exception:
            return False, None
    if t == 'integer':
        try:
            if isinstance(value, bool):
                return False, None
            return True, int(str(value).strip())
        except Exception:
            return False, None
    if t == 'boolean':
        if isinstance(value, bool):
            return True, value
        s = str(value).strip().lower()
        if s in {'true', '1', 'yes', 'y'}:
            return True, True
        if s in {'false', '0', 'no', 'n'}:
            return True, False
        return False, None
    if t == 'date':
        s = str(value).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(s, fmt)
                return True, dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                continue
        return False, None
    if t == 'url':
        s = str(value).strip()
        return (_is_valid_url(s), s if _is_valid_url(s) else None)
    return True, value


def _apply_regex(value: Any, pattern: str) -> bool:
    if value is None:
        return True
    try:
        return bool(re.match(pattern, str(value)))
    except Exception:
        return False


def run_validation(df: pd.DataFrame, rules_path: str = 'config/validation_rules.yaml') -> Tuple[pd.DataFrame, Dict[str, Any]]:
    rules = _load_rules(rules_path)
    if df is None or df.empty:
        metrics = {
            'total_input_rows': 0,
            'total_valid_rows': 0,
            'total_dropped_rows': 0,
            'invalid_by_field': {},
        }
        return df, metrics

    df = df.copy()
    invalid_by_field: Dict[str, int] = {field: 0 for field in rules.keys()}

    for field, rule in rules.items():
        expected_type = rule.get('type')
        regex = rule.get('regex')

        if field not in df.columns:
            df[field] = None

        coerced: list = []
        invalid_count = 0
        for val in df[field].tolist():
            is_valid, v = _coerce_type(val, expected_type) if expected_type else (True, val)
            if is_valid and regex:
                if not _apply_regex(v, regex):
                    is_valid = False
                    v = None
            if not is_valid:
                invalid_count += 1
                v = None
            coerced.append(v)
        df[field] = coerced
        invalid_by_field[field] = invalid_count

    required_fields = [f for f, r in rules.items() if r.get('required')]
    if required_fields:
        before = len(df)
        mask_valid = pd.Series([True] * len(df))
        for f in required_fields:
            mask_valid &= df[f].notna()
        df = df[mask_valid].reset_index(drop=True)
        dropped = before - len(df)
    else:
        dropped = 0

    metrics = {
        'total_input_rows': int(len(mask_valid)) if 'mask_valid' in locals() else int(len(df)),
        'total_valid_rows': int(len(df)),
        'total_dropped_rows': int(dropped),
        'invalid_by_field': invalid_by_field,
    }
    return df, metrics


