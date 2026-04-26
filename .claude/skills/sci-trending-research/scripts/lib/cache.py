"""Caching utilities for last30days skill.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path.home() / ".cache" / "last30days"
DEFAULT_TTL_HOURS = 24
MODEL_CACHE_TTL_DAYS = 7


def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_key(topic: str, from_date: str, to_date: str, sources: str) -> str:
    key_data = f"{topic}|{from_date}|{to_date}|{sources}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def get_cache_path(cache_key: str) -> Path:
    return CACHE_DIR / f"{cache_key}.json"


def is_cache_valid(cache_path: Path, ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
    if not cache_path.exists():
        return False
    try:
        stat = cache_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - mtime).total_seconds() / 3600
        return age_hours < ttl_hours
    except OSError:
        return False


def load_cache(cache_key: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> Optional[dict]:
    cache_path = get_cache_path(cache_key)
    if not is_cache_valid(cache_path, ttl_hours):
        return None
    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_cache_age_hours(cache_path: Path) -> Optional[float]:
    if not cache_path.exists():
        return None
    try:
        stat = cache_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - mtime).total_seconds() / 3600
    except OSError:
        return None


def load_cache_with_age(cache_key: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> tuple:
    cache_path = get_cache_path(cache_key)
    if not is_cache_valid(cache_path, ttl_hours):
        return None, None
    age = get_cache_age_hours(cache_path)
    try:
        with open(cache_path, 'r') as f:
            return json.load(f), age
    except (json.JSONDecodeError, OSError):
        return None, None


def save_cache(cache_key: str, data: dict):
    ensure_cache_dir()
    cache_path = get_cache_path(cache_key)
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass


def clear_cache():
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass


MODEL_CACHE_FILE = CACHE_DIR / "model_selection.json"


def load_model_cache() -> dict:
    if not is_cache_valid(MODEL_CACHE_FILE, MODEL_CACHE_TTL_DAYS * 24):
        return {}
    try:
        with open(MODEL_CACHE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_model_cache(data: dict):
    ensure_cache_dir()
    try:
        with open(MODEL_CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass


def get_cached_model(provider: str) -> Optional[str]:
    cache = load_model_cache()
    return cache.get(provider)


def set_cached_model(provider: str, model: str):
    cache = load_model_cache()
    cache[provider] = model
    cache['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_model_cache(cache)
