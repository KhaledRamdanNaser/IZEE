MOBILITY_CAIRO_MAPS_EN_URL = "https://www.mobilitycairo.com/en/travel-information/maps"
MOBILITY_CAIRO_MAPS_AR_URL = "https://www.mobilitycairo.com/ar/travel-information/maps"


OFFICIAL_STATION_AREA_MAPS = [
    {
        "station_name_en": "Adly Mansour",
        "station_name_ar": "عدلي منصور",
        "aliases": ["around adly mansour", "محطة عدلي منصور", "المحيطة عدلي منصور"],
    },
    {
        "station_name_en": "El Haykestep",
        "station_name_ar": "الهايكستب",
        "aliases": ["haykstep", "haykestep", "around haykstep", "محطة الهايكستب"],
    },
    {
        "station_name_en": "Omar Ibn El Khattab",
        "station_name_ar": "عمر بن الخطاب",
        "aliases": ["omar ibn el khatab", "around omar ibn el khatab", "محطة عمر بن الخطاب"],
    },
    {
        "station_name_en": "Qubaa",
        "station_name_ar": "قباء",
        "aliases": ["qubaa", "around qubaa", "محطة قباء"],
    },
    {
        "station_name_en": "Hesham Barakat",
        "station_name_ar": "هشام بركات",
        "aliases": ["hisham barakat", "around hisham barakat", "محطة هشام بركات"],
    },
    {
        "station_name_en": "El Nozha",
        "station_name_ar": "النزهة",
        "aliases": ["nozha", "around el nozha", "محطة النزهة"],
    },
    {
        "station_name_en": "El Shams Club",
        "station_name_ar": "نادي الشمس",
        "aliases": ["shams club", "around el shams club", "محطة نادي الشمس"],
    },
    {
        "station_name_en": "Alf Maskan",
        "station_name_ar": "ألف مسكن",
        "aliases": ["alf masken", "around alf maskan", "محطة ألف مسكن"],
    },
    {
        "station_name_en": "Heliopolis",
        "station_name_ar": "هليوبوليس",
        "aliases": ["around heliopolis", "محطة هليوبوليس"],
    },
    {
        "station_name_en": "Haroun",
        "station_name_ar": "هارون",
        "aliases": ["around haroun", "محطة هارون"],
    },
    {
        "station_name_en": "El Ahram",
        "station_name_ar": "الأهرام",
        "aliases": ["al ahram", "around al ahram", "around el ahram", "محطة الأهرام"],
    },
    {
        "station_name_en": "Kolleyet El Banat",
        "station_name_ar": "كلية البنات",
        "aliases": ["kolleyet el banat", "koleyat el banat", "محطة كلية البنات"],
    },
    {
        "station_name_en": "Stadium",
        "station_name_ar": "الإستاد",
        "aliases": ["stadium", "around stadium", "محطة الإستاد"],
    },
    {
        "station_name_en": "Fair Zone",
        "station_name_ar": "أرض المعارض",
        "aliases": ["cairo fair", "fair zone", "around fair zone", "محطة أرض المعارض"],
    },
    {
        "station_name_en": "Abassiya",
        "station_name_ar": "العباسية",
        "aliases": ["abbasia", "abassiya", "around abbasia", "محطة العباسية"],
    },
    {
        "station_name_en": "Abdou Pasha",
        "station_name_ar": "عبده باشا",
        "aliases": ["abdo pasha", "abdou pasha", "around abdou pasha", "محطة عبده باشا"],
    },
    {
        "station_name_en": "El Geish",
        "station_name_ar": "الجيش",
        "aliases": ["el giesh", "around el geish", "محطة الجيش"],
    },
    {
        "station_name_en": "Bab El Shaariya",
        "station_name_ar": "باب الشعرية",
        "aliases": ["bab el shariaa", "bab el shaariya", "محطة باب الشعرية"],
    },
    {
        "station_name_en": "Attaba",
        "station_name_ar": "العتبة",
        "aliases": ["attaba", "around attaba", "محطة العتبة"],
    },
    {
        "station_name_en": "Nasser",
        "station_name_ar": "ناصر",
        "aliases": ["nasser", "محطة ناصر"],
    },
    {
        "station_name_en": "Maspero",
        "station_name_ar": "ماسبيرو",
        "aliases": ["maspero", "محطة ماسبيرو"],
    },
    {
        "station_name_en": "Safaa Hegazy",
        "station_name_ar": "صفاء حجازي",
        "aliases": ["safaa hegazy", "محطة صفاء حجازي"],
    },
    {
        "station_name_en": "Kit-Kat",
        "station_name_ar": "الكيت كات",
        "aliases": ["kitkat", "kit-kat", "kit kat", "محطة الكيت كات"],
    },
]


def normalize_station_text(value):
    return str(value or "").strip().casefold()


def station_area_records():
    records = []

    for item in OFFICIAL_STATION_AREA_MAPS:
        aliases = [
            item["station_name_en"],
            item["station_name_ar"],
            *item.get("aliases", []),
        ]
        records.append({
            "station_name_en": item["station_name_en"],
            "station_name_ar": item["station_name_ar"],
            "aliases": aliases,
            "nearby_landmarks": item.get("nearby_landmarks", []),
            "source_urls": [
                MOBILITY_CAIRO_MAPS_EN_URL,
                MOBILITY_CAIRO_MAPS_AR_URL,
            ],
            "confidence": "official_station_area_map",
            "usage": "metadata_only",
        })

    return records


STATION_AREA_RECORDS = station_area_records()


def station_area_metadata_for_stop(stop_name):
    normalized_stop_name = normalize_station_text(stop_name)

    if not normalized_stop_name:
        return None

    for record in STATION_AREA_RECORDS:
        normalized_aliases = [
            normalize_station_text(alias)
            for alias in record["aliases"]
        ]

        if any(alias and alias in normalized_stop_name for alias in normalized_aliases):
            return record

        if any(normalized_stop_name and normalized_stop_name in alias for alias in normalized_aliases):
            return record

    return None

