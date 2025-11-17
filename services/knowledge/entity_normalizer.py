from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

_TOKEN_PATTERN = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"the", "a", "an", "and", "or", "for", "of", "to"}

_TOKEN_SUBSTITUTIONS = {
    "clients": "customer",
    "client": "customer",
    "customers": "customer",
    "customer": "customer",
    "acct": "account",
    "accts": "account",
    "accounts": "account",
    "teams": "team",
    "team": "team",
    "pm": "product-manager",
    "pms": "product-manager",
    "enterprise": "enterprise",
}


@dataclass(frozen=True)
class NormalizedEntityName:
    """Normalized representation for comparing entity mentions."""

    canonical_name: str
    tokens: Tuple[str, ...]
    original: str


def normalize_entity_name(raw: str) -> NormalizedEntityName:
    """Normalize arbitrary entity text into a canonical slug."""
    stripped = raw.strip()
    lowered = stripped.lower()
    cleaned = _TOKEN_PATTERN.sub(" ", lowered)

    tokens = tuple(
        _normalize_token(token)
        for token in cleaned.split(" ")
        if token and token not in _STOPWORDS
    )
    filtered_tokens = tuple(token for token in tokens if token)

    if filtered_tokens:
        canonical = "-".join(filtered_tokens)
    else:
        fallback = _TOKEN_PATTERN.sub("-", lowered).strip("-")
        canonical = fallback or "entity"

    return NormalizedEntityName(
        canonical_name=canonical,
        tokens=filtered_tokens,
        original=stripped,
    )


def _normalize_token(token: str) -> str:
    base = token.strip()
    if not base:
        return ""
    base = _TOKEN_SUBSTITUTIONS.get(base, base)
    if base.endswith("ies") and len(base) > 3:
        base = base[:-3] + "y"
    elif base.endswith("ses") and len(base) > 3:
        base = base[:-2]
    elif base.endswith("s") and len(base) > 3 and not base.endswith("ss"):
        base = base[:-1]
    return base.replace("_", "-")
