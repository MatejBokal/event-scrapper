"""Generate localized, region-aware search queries."""

from __future__ import annotations

from backend.config import MAX_QUERIES
from backend.models import SearchParams
from backend.regions import RegionProfile, get_field_terms, get_region_profile

MONTH_QUERY_SAMPLE_SIZE = 3
MONTH_QUERY_SLOTS = 6

ORGANIZER_SUFFIXES: dict[str, list[str]] = {
    "en": ["organizer contact", "organising committee", "event manager"],
    "sl": ["organizator", "organizator dogodka", "organizacijski odbor"],
    "de": ["Veranstalter", "Organisator Kontakt"],
    "hr": ["organizator", "organizator događaja"],
    "fr": ["organisateur", "comité d'organisation"],
    "it": ["organizzatore", "comitato organizzatore"],
    "es": ["organizador", "comité organizador"],
    "pl": ["organizator", "komitet organizacyjny"],
    "cs": ["organizátor", "organizační výbor"],
    "nl": ["organisator", "organisatiecomité"],
    "pt": ["organizador", "comité organizador"],
}

MONTH_NAMES: dict[str, list[str]] = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "sl": [
        "januar",
        "februar",
        "marec",
        "april",
        "maj",
        "junij",
        "julij",
        "avgust",
        "september",
        "oktober",
        "november",
        "december",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
    "hr": [
        "siječanj",
        "veljača",
        "ožujak",
        "travanj",
        "svibanj",
        "lipanj",
        "srpanj",
        "kolovoz",
        "rujan",
        "listopad",
        "studeni",
        "prosinac",
    ],
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "it": [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ],
    "es": [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ],
    "pl": [
        "styczeń",
        "luty",
        "marzec",
        "kwiecień",
        "maj",
        "czerwiec",
        "lipiec",
        "sierpień",
        "wrzesień",
        "październik",
        "listopad",
        "grudzień",
    ],
    "cs": [
        "leden",
        "únor",
        "březen",
        "duben",
        "květen",
        "červen",
        "červenec",
        "srpen",
        "září",
        "říjen",
        "listopad",
        "prosinec",
    ],
    "nl": [
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ],
    "pt": [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ],
}


def _all_months_in_range(start_month: str, end_month: str) -> list[tuple[int, int]]:
    if not start_month or not end_month:
        return []

    try:
        start_year, start_m = map(int, start_month.split("-"))
        end_year, end_m = map(int, end_month.split("-"))
    except ValueError:
        return []

    months: list[tuple[int, int]] = []
    year, month = start_year, start_m
    while (year, month) <= (end_year, end_m):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _sample_query_months(
    start_month: str,
    end_month: str,
    max_samples: int = MONTH_QUERY_SAMPLE_SIZE,
) -> list[tuple[int, int]]:
    months = _all_months_in_range(start_month, end_month)
    if not months:
        return []
    if len(months) <= max_samples:
        return months

    indices = sorted({0, len(months) // 2, len(months) - 1})
    return [months[index] for index in indices[:max_samples]]


def _year_from_range(start_month: str, end_month: str) -> str:
    if start_month:
        return start_month.split("-")[0]
    if end_month:
        return end_month.split("-")[0]
    return ""


def _month_label(year: int, month: int, lang: str) -> str:
    names = MONTH_NAMES.get(lang, MONTH_NAMES["en"])
    if month < 1 or month > 12:
        return str(year)
    return f"{names[month - 1]} {year}"


def _field_term_for_language(lang: str, field_terms: list[str]) -> str:
    if lang == "en":
        return field_terms[0]
    if len(field_terms) > 1:
        return field_terms[1]
    return field_terms[0]


def _dedupe(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _queries_for_language(
    lang: str,
    profile: RegionProfile,
    field_term: str,
    locations: list[str],
    year: str,
) -> list[str]:
    synonyms = profile.event_synonyms.get(lang, profile.event_synonyms["en"])
    suffixes = ORGANIZER_SUFFIXES.get(lang, ORGANIZER_SUFFIXES["en"])
    queries: list[str] = []

    for location in locations[:3]:
        for synonym in synonyms[:2]:
            base = f"{field_term} {synonym} {location}"
            if year:
                queries.append(f"{base} {year}".strip())
            queries.append(base.strip())

    for suffix in suffixes[:1]:
        target = locations[0] if locations else profile.display_name
        if year:
            queries.append(f"{field_term} {suffix} {target} {year}".strip())
        queries.append(f"{field_term} {suffix} {target}".strip())

    return queries


def _build_month_queries(
    profile: RegionProfile,
    field_terms: list[str],
    locations: list[str],
    sampled_months: list[tuple[int, int]],
) -> list[str]:
    if not sampled_months:
        return []

    queries: list[str] = []
    languages = list(profile.languages[:2])
    cities = locations[:2] if len(languages) == 1 else locations[:1]
    reserve_organizer = bool(cities)
    conference_slots = MONTH_QUERY_SLOTS - 1 if reserve_organizer else MONTH_QUERY_SLOTS

    for year, month_num in sampled_months:
        for lang in languages:
            field_term = _field_term_for_language(lang, field_terms)
            synonyms = profile.event_synonyms.get(lang, profile.event_synonyms["en"])
            synonym = synonyms[0]
            month_label = _month_label(year, month_num, lang)

            for city in cities:
                queries.append(f"{field_term} {synonym} {city} {month_label}".strip())
                if len(queries) >= conference_slots:
                    break
            if len(queries) >= conference_slots:
                break
        if len(queries) >= conference_slots:
            break

    if reserve_organizer:
        primary_lang = languages[0]
        suffixes = ORGANIZER_SUFFIXES.get(primary_lang, ORGANIZER_SUFFIXES["en"])
        year, month_num = sampled_months[0]
        field_term = _field_term_for_language(primary_lang, field_terms)
        month_label = _month_label(year, month_num, primary_lang)
        queries.append(
            f"{field_term} {suffixes[0]} {cities[0]} {month_label}".strip()
        )

    return queries[:MONTH_QUERY_SLOTS]


def build_queries(params: SearchParams) -> list[str]:
    profile = get_region_profile(params.region, params.custom_region)
    field_terms = get_field_terms(params.field, profile)
    year = _year_from_range(params.start_month, params.end_month)
    sampled_months = _sample_query_months(params.start_month, params.end_month)
    locations: list[str] = list(profile.cities) or [profile.display_name]

    month_queries = _build_month_queries(profile, field_terms, locations, sampled_months)

    per_language: dict[str, list[str]] = {}
    for lang in profile.languages:
        field_term = _field_term_for_language(lang, field_terms)
        per_language[lang] = _queries_for_language(
            lang, profile, field_term, locations, year
        )

    base_queries: list[str] = []
    max_len = max((len(items) for items in per_language.values()), default=0)
    for index in range(max_len):
        for lang in profile.languages:
            items = per_language.get(lang, [])
            if index < len(items):
                base_queries.append(items[index])

    if year:
        base_queries.append(
            f"{params.field.strip()} conference {profile.display_name} {year}".strip()
        )

    combined = month_queries + base_queries
    return _dedupe(combined)[:MAX_QUERIES]
