"""Event synonym packs shared by search queries and keyword gate."""

from __future__ import annotations

from backend.config import CONFERENCE_KEYWORDS
from backend.query_builder import EXTRA_EVENT_SYNONYMS
from backend.regions import RegionProfile, _EN_EVENTS, get_region_profile


def event_keywords_for_profile(
    profile: RegionProfile,
    *,
    extra_synonyms: dict[str, list[str]] | None = None,
) -> list[str]:
    """EN + profile language synonyms (+ settings extras + CONFERENCE_KEYWORDS)."""
    found: set[str] = set()

    for syn in _EN_EVENTS:
        found.add(syn.casefold())
    for syn in CONFERENCE_KEYWORDS:
        found.add(str(syn).casefold())

    for _lang, synonyms in profile.event_synonyms.items():
        for syn in synonyms:
            cleaned = str(syn).strip().casefold()
            if cleaned:
                found.add(cleaned)

    extras = extra_synonyms if extra_synonyms is not None else EXTRA_EVENT_SYNONYMS
    if extras:
        # Always merge English extras; also extras for profile languages.
        langs = {"en", *profile.languages}
        for lang in langs:
            for syn in extras.get(lang, []) or []:
                cleaned = str(syn).strip().casefold()
                if cleaned:
                    found.add(cleaned)

    return sorted(found)


def event_keywords_for_region(region: str, custom_region: str = "") -> list[str]:
    profile = get_region_profile(region, custom_region)
    return event_keywords_for_profile(profile)
