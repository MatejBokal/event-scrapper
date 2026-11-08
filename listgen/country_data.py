"""Load per-country city lists and region metadata for bulk list generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.regions import REGION_PROFILES, RegionProfile, _en_synonyms, build_custom_profile

LISTGEN_ROOT = Path(__file__).resolve().parent
COUNTRIES_DIR = LISTGEN_ROOT / "countries"
EUROPE_DATA_PATH = COUNTRIES_DIR / "europe.json"


def _load_europe_data() -> dict[str, Any]:
    with EUROPE_DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def available_countries() -> list[str]:
    data = _load_europe_data()
    return sorted(data.keys())


def get_country_entry(country_name: str) -> dict[str, Any]:
    data = _load_europe_data()
    if country_name not in data:
        known = ", ".join(sorted(data.keys()))
        raise KeyError(f"Unknown country '{country_name}'. Available: {known}")
    return data[country_name]


def get_cities(country_name: str, *, test_run: bool = False, test_city: str = "") -> list[str]:
    entry = get_country_entry(country_name)
    all_cities = list(entry.get("cities", []))
    if not all_cities:
        raise ValueError(f"No cities defined for country '{country_name}'")

    if not test_run:
        return all_cities

    preferred = test_city.strip()
    if preferred:
        if preferred not in all_cities:
            raise ValueError(
                f"test_city '{preferred}' is not in {country_name} city list: {', '.join(all_cities)}"
            )
        return [preferred]
    return [all_cities[0]]


def get_city_allowlist(country_name: str) -> list[str]:
    """Expanded venue/city names used for page presence matching (not search fanout)."""
    entry = get_country_entry(country_name)
    allowlist = list(entry.get("city_allowlist") or [])
    if allowlist:
        return allowlist
    cities = list(entry.get("cities") or [])
    if not cities:
        raise ValueError(f"No city_allowlist/cities defined for country '{country_name}'")
    return cities


def get_event_keywords(country_name: str) -> list[str]:
    """Event synonyms for keyword gate (EN + country languages + settings extras)."""
    from backend.event_keywords import event_keywords_for_profile

    profile = get_region_profile_for_country(country_name)
    return event_keywords_for_profile(profile)


def get_region_profile_for_country(country_name: str) -> RegionProfile:
    entry = get_country_entry(country_name)
    region_key = entry.get("region_key") or country_name
    if region_key in REGION_PROFILES:
        return REGION_PROFILES[region_key]

    cities = tuple(entry.get("cities", []))
    country_names = tuple(entry.get("country_names", [country_name.lower()]))
    return RegionProfile(
        key=country_name.lower().replace(" ", "_"),
        display_name=country_name,
        cities=cities,
        country_names=country_names,
        tlds=tuple(entry.get("tlds", [])),
        phone_prefixes=tuple(entry.get("phone_prefixes", [])),
        languages=tuple(entry.get("languages", ["en"])),
        event_synonyms=entry.get("event_synonyms") or _en_synonyms(),
        search_region=entry.get("search_region", "wt-wt"),
        negative_locations=tuple(entry.get("negative_locations", [])),
    )
