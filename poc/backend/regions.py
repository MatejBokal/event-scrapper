"""Region profiles for localized query expansion and geo filtering."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegionProfile:
    key: str
    display_name: str
    cities: tuple[str, ...]
    country_names: tuple[str, ...]
    tlds: tuple[str, ...]
    phone_prefixes: tuple[str, ...]
    languages: tuple[str, ...]
    event_synonyms: dict[str, tuple[str, ...]]
    search_region: str = "wt-wt"
    negative_locations: tuple[str, ...] = field(default_factory=tuple)


FIELD_TRANSLATIONS: dict[str, dict[str, str]] = {
    "healthcare": {
        "en": "healthcare",
        "sl": "zdravstvo",
        "de": "Gesundheit",
        "hr": "zdravstvo",
        "fr": "santé",
        "it": "sanità",
        "pl": "zdrowie",
        "cs": "zdravotnictví",
        "es": "salud",
    },
    "pharmaceuticals": {"en": "pharmaceutical", "sl": "farmacevtska", "de": "Pharma", "fr": "pharmaceutique"},
    "pharma": {"en": "pharma", "sl": "farmacija", "de": "Pharma", "fr": "pharma"},
    "security": {
        "en": "security",
        "sl": "varnost",
        "de": "Sicherheit",
        "hr": "sigurnost",
        "fr": "sécurité",
        "pl": "bezpieczeństwo",
        "cs": "bezpečnost",
    },
    "cybersecurity": {
        "en": "cybersecurity",
        "sl": "kibernetska varnost",
        "de": "Cybersicherheit",
        "fr": "cybersécurité",
    },
    "it": {"en": "IT", "sl": "informacijska tehnologija", "de": "IT", "fr": "informatique"},
    "ai": {"en": "AI", "sl": "umetna inteligenca", "de": "KI", "fr": "intelligence artificielle"},
    "artificial intelligence": {
        "en": "artificial intelligence",
        "sl": "umetna inteligenca",
        "de": "künstliche Intelligenz",
        "fr": "intelligence artificielle",
    },
}

_EN_EVENTS = ("conference", "congress", "summit", "symposium", "event", "fair")
_EN_EVENTS_EXPO = ("conference", "congress", "summit", "symposium", "convention", "expo")


def _en_synonyms(*extra: str) -> dict[str, tuple[str, ...]]:
    return {"en": _EN_EVENTS + extra if extra else _EN_EVENTS}


REGION_PROFILES: dict[str, RegionProfile] = {
    # --- Adriatic & Central Europe (Confiva home market) ---
    "Slovenia": RegionProfile(
        key="slovenia",
        display_name="Slovenia",
        cities=("Ljubljana", "Maribor", "Celje", "Kranj", "Koper"),
        country_names=("slovenia", "sloveniji", "slovenian", "slovenski", "slovenska", "slovensko"),
        tlds=(".si",),
        phone_prefixes=("+386", "00386"),
        languages=("en", "sl"),
        event_synonyms={
            "en": _EN_EVENTS,
            "sl": ("konferenca", "kongres", "simpozij", "dogodek", "sejem"),
        },
        search_region="sl-sl",
        negative_locations=("zagreb", "hyderabad", "india"),
    ),
    "Croatia": RegionProfile(
        key="croatia",
        display_name="Croatia",
        cities=("Zagreb", "Split", "Rijeka", "Osijek", "Dubrovnik"),
        country_names=("croatia", "croatian", "hrvatska", "hrvatskoj"),
        tlds=(".hr",),
        phone_prefixes=("+385", "00385"),
        languages=("en", "hr"),
        event_synonyms={
            "en": _EN_EVENTS,
            "hr": ("konferencija", "kongres", "simpozij", "događaj"),
        },
        search_region="hr-hr",
    ),
    "Bosnia and Herzegovina": RegionProfile(
        key="bosnia",
        display_name="Bosnia and Herzegovina",
        cities=("Sarajevo", "Banja Luka", "Mostar", "Tuzla"),
        country_names=("bosnia", "herzegovina", "bosna", "hercegovina"),
        tlds=(".ba",),
        phone_prefixes=("+387",),
        languages=("en", "bs"),
        event_synonyms={
            "en": _EN_EVENTS,
            "bs": ("konferencija", "kongres", "simpozij"),
        },
        search_region="wt-wt",
    ),
    "Serbia": RegionProfile(
        key="serbia",
        display_name="Serbia",
        cities=("Belgrade", "Novi Sad", "Niš", "Kragujevac"),
        country_names=("serbia", "serbian", "srbija", "beograd"),
        tlds=(".rs",),
        phone_prefixes=("+381",),
        languages=("en", "sr"),
        event_synonyms={
            "en": _EN_EVENTS,
            "sr": ("konferencija", "kongres", "simpozijum"),
        },
        search_region="wt-wt",
    ),
    "Montenegro": RegionProfile(
        key="montenegro",
        display_name="Montenegro",
        cities=("Podgorica", "Budva", "Kotor", "Nikšić"),
        country_names=("montenegro", "crna gora", "podgorica"),
        tlds=(".me",),
        phone_prefixes=("+382",),
        languages=("en",),
        event_synonyms=_en_synonyms(),
        search_region="wt-wt",
    ),
    "North Macedonia": RegionProfile(
        key="north_macedonia",
        display_name="North Macedonia",
        cities=("Skopje", "Bitola", "Ohrid"),
        country_names=("north macedonia", "macedonia", "skopje", "македонија"),
        tlds=(".mk",),
        phone_prefixes=("+389",),
        languages=("en",),
        event_synonyms=_en_synonyms(),
        search_region="wt-wt",
    ),
    "Austria": RegionProfile(
        key="austria",
        display_name="Austria",
        cities=("Vienna", "Graz", "Salzburg", "Innsbruck", "Linz"),
        country_names=("austria", "austrian", "österreich", "osterreich", "wien"),
        tlds=(".at",),
        phone_prefixes=("+43", "0043"),
        languages=("en", "de"),
        event_synonyms={
            "en": _EN_EVENTS,
            "de": ("konferenz", "kongress", "symposium", "veranstaltung"),
        },
        search_region="at-de",
    ),
    "Hungary": RegionProfile(
        key="hungary",
        display_name="Hungary",
        cities=("Budapest", "Debrecen", "Szeged", "Pécs"),
        country_names=("hungary", "hungarian", "magyarország", "budapest"),
        tlds=(".hu",),
        phone_prefixes=("+36",),
        languages=("en", "hu"),
        event_synonyms={
            "en": _EN_EVENTS,
            "hu": ("konferencia", "kongresszus", "szimpózium"),
        },
        search_region="wt-wt",
    ),
    "Slovakia": RegionProfile(
        key="slovakia",
        display_name="Slovakia",
        cities=("Bratislava", "Košice", "Žilina", "Nitra"),
        country_names=("slovakia", "slovak", "slovensko", "bratislava"),
        tlds=(".sk",),
        phone_prefixes=("+421",),
        languages=("en", "sk"),
        event_synonyms={
            "en": _EN_EVENTS,
            "sk": ("konferencia", "kongres", "sympózium"),
        },
        search_region="wt-wt",
    ),
    "Czech Republic": RegionProfile(
        key="czechia",
        display_name="Czech Republic",
        cities=("Prague", "Brno", "Ostrava", "Plzeň"),
        country_names=("czech", "czechia", "česko", "prague", "praha"),
        tlds=(".cz",),
        phone_prefixes=("+420",),
        languages=("en", "cs"),
        event_synonyms={
            "en": _EN_EVENTS,
            "cs": ("konference", "kongres", "sympozium"),
        },
        search_region="cz-cs",
    ),
    "Poland": RegionProfile(
        key="poland",
        display_name="Poland",
        cities=("Warsaw", "Kraków", "Wrocław", "Gdańsk", "Poznań"),
        country_names=("poland", "polish", "polska", "warsaw", "warszawa"),
        tlds=(".pl",),
        phone_prefixes=("+48",),
        languages=("en", "pl"),
        event_synonyms={
            "en": _EN_EVENTS,
            "pl": ("konferencja", "kongres", "sympozjum"),
        },
        search_region="pl-pl",
    ),
    # --- Western Europe ---
    "Germany": RegionProfile(
        key="germany",
        display_name="Germany",
        cities=("Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"),
        country_names=("germany", "german", "deutschland", "deutsche"),
        tlds=(".de",),
        phone_prefixes=("+49", "0049"),
        languages=("en", "de"),
        event_synonyms={
            "en": ("conference", "congress", "summit", "symposium", "trade fair"),
            "de": ("konferenz", "kongress", "symposium", "messe", "veranstaltung"),
        },
        search_region="de-de",
    ),
    "Switzerland": RegionProfile(
        key="switzerland",
        display_name="Switzerland",
        cities=("Zurich", "Geneva", "Basel", "Bern", "Lausanne"),
        country_names=("switzerland", "swiss", "schweiz", "suisse", "zürich"),
        tlds=(".ch",),
        phone_prefixes=("+41",),
        languages=("en", "de", "fr"),
        event_synonyms={
            "en": _EN_EVENTS,
            "de": ("konferenz", "kongress", "messe"),
            "fr": ("conférence", "congrès", "symposium"),
        },
        search_region="ch-de",
    ),
    "France": RegionProfile(
        key="france",
        display_name="France",
        cities=("Paris", "Lyon", "Marseille", "Toulouse", "Nice"),
        country_names=("france", "french", "français", "paris"),
        tlds=(".fr",),
        phone_prefixes=("+33",),
        languages=("en", "fr"),
        event_synonyms={
            "en": _EN_EVENTS,
            "fr": ("conférence", "congrès", "sommet", "symposium", "salon"),
        },
        search_region="fr-fr",
    ),
    "Belgium": RegionProfile(
        key="belgium",
        display_name="Belgium",
        cities=("Brussels", "Antwerp", "Ghent", "Liège"),
        country_names=("belgium", "belgian", "belgique", "brussels", "bruxelles"),
        tlds=(".be",),
        phone_prefixes=("+32",),
        languages=("en", "fr", "nl"),
        event_synonyms={
            "en": _EN_EVENTS,
            "fr": ("conférence", "congrès"),
            "nl": ("conferentie", "congres"),
        },
        search_region="wt-wt",
    ),
    "Netherlands": RegionProfile(
        key="netherlands",
        display_name="Netherlands",
        cities=("Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"),
        country_names=("netherlands", "dutch", "holland", "nederland", "amsterdam"),
        tlds=(".nl",),
        phone_prefixes=("+31",),
        languages=("en", "nl"),
        event_synonyms={
            "en": _EN_EVENTS,
            "nl": ("conferentie", "congres", "symposium", "beurs"),
        },
        search_region="nl-nl",
    ),
    "Luxembourg": RegionProfile(
        key="luxembourg",
        display_name="Luxembourg",
        cities=("Luxembourg City",),
        country_names=("luxembourg", "luxembourgish"),
        tlds=(".lu",),
        phone_prefixes=("+352",),
        languages=("en", "fr", "de"),
        event_synonyms={
            "en": _EN_EVENTS,
            "fr": ("conférence", "congrès"),
        },
        search_region="wt-wt",
    ),
    "Italy": RegionProfile(
        key="italy",
        display_name="Italy",
        cities=("Rome", "Milan", "Naples", "Turin", "Bologna"),
        country_names=("italy", "italian", "italia", "roma", "milano"),
        tlds=(".it",),
        phone_prefixes=("+39",),
        languages=("en", "it"),
        event_synonyms={
            "en": _EN_EVENTS,
            "it": ("conferenza", "congresso", "simposio", "fiera"),
        },
        search_region="it-it",
    ),
    "Spain": RegionProfile(
        key="spain",
        display_name="Spain",
        cities=("Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"),
        country_names=("spain", "spanish", "españa", "madrid", "barcelona"),
        tlds=(".es",),
        phone_prefixes=("+34",),
        languages=("en", "es"),
        event_synonyms={
            "en": _EN_EVENTS,
            "es": ("conferencia", "congreso", "simposio", "feria"),
        },
        search_region="es-es",
    ),
    "Portugal": RegionProfile(
        key="portugal",
        display_name="Portugal",
        cities=("Lisbon", "Porto", "Braga", "Coimbra"),
        country_names=("portugal", "portuguese", "lisboa", "porto"),
        tlds=(".pt",),
        phone_prefixes=("+351",),
        languages=("en", "pt"),
        event_synonyms={
            "en": _EN_EVENTS,
            "pt": ("conferência", "congresso", "simpósio"),
        },
        search_region="pt-pt",
    ),
    "United Kingdom": RegionProfile(
        key="uk",
        display_name="United Kingdom",
        cities=("London", "Manchester", "Birmingham", "Edinburgh", "Bristol"),
        country_names=("united kingdom", "uk", "britain", "british", "england", "scotland"),
        tlds=(".uk", ".co.uk"),
        phone_prefixes=("+44", "0044"),
        languages=("en",),
        event_synonyms={"en": ("conference", "congress", "summit", "symposium", "event", "exhibition")},
        search_region="uk-en",
    ),
    "Ireland": RegionProfile(
        key="ireland",
        display_name="Ireland",
        cities=("Dublin", "Cork", "Galway", "Limerick"),
        country_names=("ireland", "irish", "éire", "dublin"),
        tlds=(".ie",),
        phone_prefixes=("+353",),
        languages=("en",),
        event_synonyms=_en_synonyms(),
        search_region="ie-en",
    ),
    # --- Nordics ---
    "Denmark": RegionProfile(
        key="denmark",
        display_name="Denmark",
        cities=("Copenhagen", "Aarhus", "Odense", "Aalborg"),
        country_names=("denmark", "danish", "danmark", "copenhagen", "københavn"),
        tlds=(".dk",),
        phone_prefixes=("+45",),
        languages=("en", "da"),
        event_synonyms={
            "en": _EN_EVENTS,
            "da": ("konference", "kongres", "symposium"),
        },
        search_region="dk-da",
    ),
    "Sweden": RegionProfile(
        key="sweden",
        display_name="Sweden",
        cities=("Stockholm", "Gothenburg", "Malmö", "Uppsala"),
        country_names=("sweden", "swedish", "sverige", "stockholm"),
        tlds=(".se",),
        phone_prefixes=("+46",),
        languages=("en", "sv"),
        event_synonyms={
            "en": _EN_EVENTS,
            "sv": ("konferens", "kongress", "symposium"),
        },
        search_region="se-sv",
    ),
    "Norway": RegionProfile(
        key="norway",
        display_name="Norway",
        cities=("Oslo", "Bergen", "Trondheim", "Stavanger"),
        country_names=("norway", "norwegian", "norge", "oslo"),
        tlds=(".no",),
        phone_prefixes=("+47",),
        languages=("en", "no"),
        event_synonyms={
            "en": _EN_EVENTS,
            "no": ("konferanse", "kongress", "symposium"),
        },
        search_region="no-no",
    ),
    "Finland": RegionProfile(
        key="finland",
        display_name="Finland",
        cities=("Helsinki", "Tampere", "Turku", "Oulu"),
        country_names=("finland", "finnish", "suomi", "helsinki"),
        tlds=(".fi",),
        phone_prefixes=("+358",),
        languages=("en", "fi"),
        event_synonyms={
            "en": _EN_EVENTS,
            "fi": ("konferenssi", "kongressi", "symposium"),
        },
        search_region="fi-fi",
    ),
    # --- Southeast Europe ---
    "Romania": RegionProfile(
        key="romania",
        display_name="Romania",
        cities=("Bucharest", "Cluj-Napoca", "Timișoara", "Iași"),
        country_names=("romania", "romanian", "bucurești", "bucharest"),
        tlds=(".ro",),
        phone_prefixes=("+40",),
        languages=("en", "ro"),
        event_synonyms={
            "en": _EN_EVENTS,
            "ro": ("conferință", "congres", "simpozion"),
        },
        search_region="wt-wt",
    ),
    "Bulgaria": RegionProfile(
        key="bulgaria",
        display_name="Bulgaria",
        cities=("Sofia", "Plovdiv", "Varna", "Burgas"),
        country_names=("bulgaria", "bulgarian", "софия", "sofia"),
        tlds=(".bg",),
        phone_prefixes=("+359",),
        languages=("en", "bg"),
        event_synonyms={
            "en": _EN_EVENTS,
            "bg": ("конференция", "конгрес"),
        },
        search_region="wt-wt",
    ),
    "Greece": RegionProfile(
        key="greece",
        display_name="Greece",
        cities=("Athens", "Thessaloniki", "Patras", "Heraklion"),
        country_names=("greece", "greek", "ελλάδα", "athens"),
        tlds=(".gr",),
        phone_prefixes=("+30",),
        languages=("en", "el"),
        event_synonyms={
            "en": _EN_EVENTS,
            "el": ("συνέδριο", "σύνοδος"),
        },
        search_region="wt-wt",
    ),
    "Turkey": RegionProfile(
        key="turkey",
        display_name="Turkey",
        cities=("Istanbul", "Ankara", "Izmir", "Bursa"),
        country_names=("turkey", "turkish", "türkiye", "istanbul"),
        tlds=(".tr",),
        phone_prefixes=("+90",),
        languages=("en", "tr"),
        event_synonyms={
            "en": _EN_EVENTS,
            "tr": ("konferans", "kongre", "sempozyum"),
        },
        search_region="tr-tr",
    ),
    # --- Americas & Oceania ---
    "United States": RegionProfile(
        key="us",
        display_name="United States",
        cities=("New York", "San Francisco", "Chicago", "Boston", "Austin"),
        country_names=("united states", "usa", "u.s.", "american"),
        tlds=(".us",),
        phone_prefixes=("+1",),
        languages=("en",),
        event_synonyms={"en": _EN_EVENTS_EXPO},
        search_region="us-en",
    ),
    "Canada": RegionProfile(
        key="canada",
        display_name="Canada",
        cities=("Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"),
        country_names=("canada", "canadian", "toronto", "montreal"),
        tlds=(".ca",),
        phone_prefixes=("+1",),
        languages=("en", "fr"),
        event_synonyms={
            "en": _EN_EVENTS_EXPO,
            "fr": ("conférence", "congrès"),
        },
        search_region="ca-en",
    ),
    "Australia": RegionProfile(
        key="australia",
        display_name="Australia",
        cities=("Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"),
        country_names=("australia", "australian", "sydney", "melbourne"),
        tlds=(".au",),
        phone_prefixes=("+61",),
        languages=("en",),
        event_synonyms=_en_synonyms("expo"),
        search_region="au-en",
    ),
    # --- Broad regions ---
    "Europe": RegionProfile(
        key="europe",
        display_name="Europe",
        cities=("Brussels", "Amsterdam", "Paris", "Berlin", "Vienna"),
        country_names=("europe", "european"),
        tlds=(),
        phone_prefixes=(),
        languages=("en",),
        event_synonyms=_en_synonyms(),
        search_region="wt-wt",
    ),
    "Asia": RegionProfile(
        key="asia",
        display_name="Asia",
        cities=("Singapore", "Tokyo", "Hong Kong", "Bangkok", "Seoul"),
        country_names=("asia", "asian"),
        tlds=(),
        phone_prefixes=(),
        languages=("en",),
        event_synonyms=_en_synonyms("expo"),
        search_region="wt-wt",
    ),
    "Worldwide": RegionProfile(
        key="worldwide",
        display_name="Worldwide",
        cities=(),
        country_names=(),
        tlds=(),
        phone_prefixes=(),
        languages=("en",),
        event_synonyms=_en_synonyms(),
        search_region="wt-wt",
    ),
}


REGION_OPTIONS = list(REGION_PROFILES.keys())


def build_custom_profile(name: str) -> RegionProfile:
    cleaned = name.strip()
    return RegionProfile(
        key="custom",
        display_name=cleaned,
        cities=(cleaned,) if cleaned else (),
        country_names=(cleaned.lower(),) if cleaned else (),
        tlds=(),
        phone_prefixes=(),
        languages=("en",),
        event_synonyms=_en_synonyms("talk"),
    )


def get_region_profile(region: str, custom_region: str = "") -> RegionProfile:
    if region == "Custom":
        return build_custom_profile(custom_region or "Custom")
    return REGION_PROFILES.get(region, build_custom_profile(region))


def get_field_terms(field: str, profile: RegionProfile) -> list[str]:
    normalized = field.strip().lower()
    terms: list[str] = [field.strip()]

    for key, translations in FIELD_TRANSLATIONS.items():
        if key in normalized or normalized in key:
            for lang in profile.languages:
                translated = translations.get(lang)
                if translated and translated not in terms:
                    terms.append(translated)
            break

    return terms
