"""Model auto-selection for last30days skill.

Adapted from https://github.com/Ronnie-Nutrition/last30days-skill
"""

import re
from typing import Dict, List, Optional, Tuple

from . import cache, http

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
OPENAI_FALLBACK_MODELS = ["gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4o"]

XAI_MODELS_URL = "https://api.x.ai/v1/models"
XAI_ALIASES = {
    "latest": "grok-4-1-fast",
    "stable": "grok-4-1-fast",
}


def parse_version(model_id: str) -> Optional[Tuple[int, ...]]:
    match = re.search(r'(\d+(?:\.\d+)*)', model_id)
    if match:
        return tuple(int(x) for x in match.group(1).split('.'))
    return None


def is_mainline_openai_model(model_id: str) -> bool:
    model_lower = model_id.lower()
    if not re.match(r'^gpt-5(\.\d+)*$', model_lower):
        return False
    excludes = ['mini', 'nano', 'chat', 'codex', 'pro', 'preview', 'turbo']
    for exc in excludes:
        if exc in model_lower:
            return False
    return True


def select_openai_model(
    api_key: str, policy: str = "auto", pin: Optional[str] = None,
    mock_models: Optional[List[Dict]] = None,
) -> str:
    if policy == "pinned" and pin:
        return pin
    cached = cache.get_cached_model("openai")
    if cached:
        return cached
    if mock_models is not None:
        models = mock_models
    else:
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = http.get(OPENAI_MODELS_URL, headers=headers)
            models = response.get("data", [])
        except http.HTTPError:
            return OPENAI_FALLBACK_MODELS[0]

    candidates = [m for m in models if is_mainline_openai_model(m.get("id", ""))]
    if not candidates:
        return OPENAI_FALLBACK_MODELS[0]

    def sort_key(m):
        version = parse_version(m.get("id", "")) or (0,)
        created = m.get("created", 0)
        return (version, created)

    candidates.sort(key=sort_key, reverse=True)
    selected = candidates[0]["id"]
    cache.set_cached_model("openai", selected)
    return selected


def select_xai_model(
    api_key: str, policy: str = "latest", pin: Optional[str] = None,
    mock_models: Optional[List[Dict]] = None,
) -> str:
    if policy == "pinned" and pin:
        return pin
    if policy in XAI_ALIASES:
        alias = XAI_ALIASES[policy]
        cached = cache.get_cached_model("xai")
        if cached:
            return cached
        cache.set_cached_model("xai", alias)
        return alias
    return XAI_ALIASES["latest"]


def get_models(
    config: Dict, mock_openai_models: Optional[List[Dict]] = None,
    mock_xai_models: Optional[List[Dict]] = None,
) -> Dict[str, Optional[str]]:
    result = {"openai": None, "xai": None}
    if config.get("OPENAI_API_KEY"):
        result["openai"] = select_openai_model(
            config["OPENAI_API_KEY"],
            config.get("OPENAI_MODEL_POLICY", "auto"),
            config.get("OPENAI_MODEL_PIN"),
            mock_openai_models,
        )
    if config.get("XAI_API_KEY"):
        result["xai"] = select_xai_model(
            config["XAI_API_KEY"],
            config.get("XAI_MODEL_POLICY", "latest"),
            config.get("XAI_MODEL_PIN"),
            mock_xai_models,
        )
    return result
