#!/usr/bin/env python3
"""Match the migogkbh.dk J-dag list to public map locations.

Overpass first, then Photon, then Nominatim. One-request-per-second on Nominatim.
"""

import json
import re
import subprocess
import time
import unicodedata
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "pubs.json"
CACHE = ROOT / "data" / "geocode-cache.json"

AREAS = [
    ("k", "København K", "Indre By"),
    ("v", "København V", "Vesterbro"),
    ("n", "Nørrebro & NV", "Nørrebro"),
    ("s", "Amager & SV", "Amager"),
    ("o", "Østerbro", "Østerbro"),
    ("frb", "Frederiksberg", "Frederiksberg"),
    ("val", "Valby & Vanløse", "Valby"),
]
AREA_LABEL = {a[0]: a[1] for a in AREAS}
AREA_SHORT = {a[0]: a[2] for a in AREAS}

# min_lat, min_lon, max_lat, max_lon — generous, used only to reject wild matches
BBOX = {
    "k": (55.666, 12.562, 55.694, 12.628),
    "v": (55.656, 12.528, 55.684, 12.578),
    "n": (55.680, 12.490, 55.732, 12.578),
    "s": (55.612, 12.500, 55.678, 12.675),
    "o": (55.686, 12.552, 55.735, 12.645),
    "frb": (55.662, 12.485, 55.708, 12.560),
    "val": (55.640, 12.445, 55.712, 12.540),
}
CENTER = {
    "k": (55.681, 12.586),
    "v": (55.670, 12.555),
    "n": (55.698, 12.543),
    "s": (55.648, 12.605),
    "o": (55.706, 12.580),
    "frb": (55.680, 12.523),
    "val": (55.668, 12.500),
}
CITY_BBOX = (55.605, 12.440, 55.745, 12.690)

PUBS = [
    ("k", "4tallet"),
    ("k", "Alpehytten"),
    ("k", "Andys Bar"),
    ("k", "Bankeråt"),
    ("k", "Barcelona Bar"),
    ("k", "BARkowski"),
    ("k", "Barrdrew"),
    ("k", "Basement Bar"),
    ("k", "Bird & The Churchkey"),
    ("k", "Borgerly"),
    ("k", "Cafe Guldhornene"),
    ("k", "Cafe Katz"),
    ("k", "Cafe Nemoland Christiania"),
    ("k", "Cafe Sofie Kælderen"),
    ("k", "Cafe Sommersko"),
    ("k", "Camping Boltens Gård"),
    ("k", "Centre Stage"),
    ("k", "Cph Downtown"),
    ("k", "Cucaracha Bar CPH"),
    ("k", "Den Jyske Ambassade"),
    ("k", "Det Elektriske Hjørne"),
    ("k", "Drop inn – Moving music"),
    ("k", "Floss"),
    ("k", "Foreningen Studenterhuset"),
    ("k", "Funchs Vinstue"),
    ("k", "Generator Hostel Copenhagen"),
    ("k", "Heidis Bier Bar"),
    ("k", "Hermans Bar"),
    ("k", "Høvlen 77"),
    ("k", "Jagtstuen"),
    ("k", "Jailhouse"),
    ("k", "Kanal Bodega"),
    ("k", "Kayak Bar"),
    ("k", "Liams Irish Pub"),
    ("k", "Masken"),
    ("k", "Mc Joys Pub"),
    ("k", "MJ Gothersgade"),
    ("k", "Mojo"),
    ("k", "Nørreport Bodega"),
    ("k", "Palmehaven"),
    ("k", "Rabalder Bar CPH"),
    ("k", "Rosengårdens Bodega"),
    ("k", "Sjus Bar CPH"),
    ("k", "Southern Cross Pub"),
    ("k", "The Dubliner"),
    ("k", "The Globe"),
    ("k", "Tyrolia Bier Klub"),
    ("k", "Victoria Pub"),
    ("k", "Wall Street Pub"),
    ("k", "Wessel Kro"),
    ("v", "Axelborg Bodega"),
    ("v", "Bar 42"),
    ("v", "Bar 180"),
    ("v", "Blomsten"),
    ("v", "Bryggerens"),
    ("v", "Cafe Ludwigsen"),
    ("v", "Cafe Skammekrogen"),
    ("v", "Camping Kødbyen"),
    ("v", "Club Mambo"),
    ("v", "Grotten"),
    ("v", "Jernbanecafeen"),
    ("v", "Larsens Plaz"),
    ("v", "Maximum"),
    ("v", "MEININGER Hotel Copenhagen"),
    ("v", "Nevermind – Axeltorv"),
    ("v", "Next – House Next Bar Copenhagen"),
    ("v", "Old Irish Pub Karaokebar"),
    ("v", "Oscar Bar og Cafe"),
    ("v", "Pinden bodega"),
    ("v", "Proud Mary CPH"),
    ("v", "Pub & Sport"),
    ("v", "Restaurant Klubben"),
    ("v", "Steel House"),
    ("v", "Studiecafeen Humlen"),
    ("v", "The Goat"),
    ("v", "The Old English Pub Karaokebar"),
    ("v", "The Old Irish Pub Vesterbrogade"),
    ("v", "The Scottish Pub"),
    ("v", "The Shamrock Inn – The Irish Pub"),
    ("v", "Zeppelin Bar"),
    ("n", "Barbarian"),
    ("n", "Baren RHK"),
    ("n", "Bip Bip Bar"),
    ("n", "Cafe Castro"),
    ("n", "Cafe Fuglereden"),
    ("n", "Cafe Heimdal"),
    ("n", "Cafe Klovnen"),
    ("n", "Cafe Lille Peter"),
    ("n", "Cafe Stefanshus"),
    ("n", "Franks Kro"),
    ("n", "Glentekroen"),
    ("n", "Léanowski Bar"),
    ("n", "Mimers Bodega"),
    ("n", "Nørre Bodega"),
    ("n", "Rust"),
    ("n", "Studenterhuset Sigurds Bar"),
    ("n", "Temple Bar"),
    ("n", "Tjilipop"),
    ("n", "Understellet"),
    ("n", "Western Bar Diligencen"),
    ("s", "Amager Pub"),
    ("s", "Anker"),
    ("s", "Cafe Engholm"),
    ("s", "Cafe Femøren"),
    ("s", "Jaguar Bodega"),
    ("s", "Post Bodegaen"),
    ("s", "Restaurant Kareten"),
    ("s", "Restaurant Sundby Sejl"),
    ("o", "Børges Bodega"),
    ("o", "Chevy's Bar"),
    ("o", "Foreningen Cafedrift"),
    ("o", "Halifax Trianglen"),
    ("o", "Hermod Bodega"),
    ("o", "Lumskebuksen"),
    ("frb", "A.V.F. Landbohøjskolen"),
    ("frb", "Alleenberg"),
    ("frb", "Bar Aksel"),
    ("frb", "Bartof Station"),
    ("frb", "Cafe Bartof"),
    ("frb", "Cafe Moccador"),
    ("frb", "Cafe Viggo"),
    ("frb", "Det Gamle Posthus"),
    ("frb", "Frederik VI"),
    ("frb", "Hos Robert"),
    ("frb", "The Old Irish Pub Smallegade"),
    ("val", "Cafe Cire"),
    ("val", "Hotel Fy & Bi"),
    ("val", "Mølle Cafeen"),
    ("val", "Nanok"),
    ("val", "Nykro"),
    ("val", "Snoopy Bodega"),
    ("val", "Støvlen"),
]

# Extra search phrases for names that are easy to miss.
HINTS = {
    "4tallet": ["4-tallet", "4 tallet bar"],
    "Andys Bar": ["Andy's Bar"],
    "BARkowski": ["Barkowski", "Bar Kowski"],
    "Barrdrew": ["Bar Drew", "Barrdrew bar"],
    "Bird & The Churchkey": ["Bird and the Churchkey"],
    "Cafe Nemoland Christiania": ["Nemoland Christiania"],
    "Cafe Sofie Kælderen": ["Cafe Sofie kælder", "Café Sofie"],
    "Camping Boltens Gård": ["Camping Boltens Gaard", "Camping bar Store Kongensgade"],
    "Cph Downtown": ["CPH Downtown"],
    "Cucaracha Bar CPH": ["Cucaracha Copenhagen"],
    "Drop inn – Moving music": ["Drop Inn København", "Drop Inn Kompagnistræde"],
    "Foreningen Studenterhuset": ["Studenterhuset Købmagergade"],
    "Heidis Bier Bar": ["Heidi's Bier Bar"],
    "Høvlen 77": ["Høvlen bar"],
    "Liams Irish Pub": ["Liam's Irish Pub"],
    "Mc Joys Pub": ["McJoy's Pub", "McJoys"],
    "MJ Gothersgade": ["MJ's Gothersgade", "MJs Gothersgade"],
    "Rabalder Bar CPH": ["Rabalder Bar"],
    "Sjus Bar CPH": ["Sjus Bar"],
    "Nevermind – Axeltorv": ["Nevermind Axeltorv"],
    "Next – House Next Bar Copenhagen": ["House Next Bar Copenhagen", "Next Bar Copenhagen"],
    "Old Irish Pub Karaokebar": ["Old Irish Pub karaoke København"],
    "Proud Mary CPH": ["Proud Mary Copenhagen"],
    "The Old English Pub Karaokebar": ["Old English Pub Copenhagen"],
    "The Old Irish Pub Vesterbrogade": ["Old Irish Pub Vesterbrogade"],
    "The Shamrock Inn – The Irish Pub": ["Shamrock Inn Copenhagen", "The Shamrock Inn"],
    "Studiecafeen Humlen": ["Humlen studiecafe", "Studiecaféen Humlen"],
    "Léanowski Bar": ["Leanowski", "Bar Léanowski"],
    "Studenterhuset Sigurds Bar": ["Sigurds Bar Nørrebro"],
    "Western Bar Diligencen": ["Diligencen Nørrebro", "Western Bar"],
    "Tjilipop": ["Tjili Pop", "Tjilipop bar"],
    "Baren RHK": ["RHK bar Nørrebro"],
    "Post Bodegaen": ["Postbodegaen"],
    "Chevy's Bar": ["Chevys Bar Østerbro", "Chevy's"],
    "Foreningen Cafedrift": ["Cafedrift Østerbro"],
    "Halifax Trianglen": ["Halifax Trianglen København"],
    "A.V.F. Landbohøjskolen": ["Landbohøjskolen Frederiksberg", "AVF Landbohøjskolen"],
    "The Old Irish Pub Smallegade": ["Old Irish Pub Smallegade Frederiksberg"],
    "Hotel Fy & Bi": ["Hotel Fy og Bi Valby"],
    "Mølle Cafeen": ["Møllecafeen Valby"],
    "Cafe Bartof": ["Café Bartof"],
    "Pub & Sport": ["Pub and Sport"],
    "Pinden bodega": ["Pinden"],
    "Larsens Plaz": ["Larsens Plads bar", "Larsens Plaz bodega"],
    "Restaurant Kareten": ["Kareten Amager"],
    "Restaurant Sundby Sejl": ["Sundby Sejl"],
    "Cafe Engholm": ["Café Engholm"],
    "Palmehaven": ["Palmehaven København"],
    "Centre Stage": ["Centre Stage København"],
    "Borgerly": ["Borgerly bar"],
    "Basement Bar": ["Basement Copenhagen"],
    "Generator Hostel Copenhagen": ["Generator Hostel Adelgade"],
    "MEININGER Hotel Copenhagen": ["MEININGER Copenhagen"],
    "Steel House": ["Steel House Copenhagen"],
    "Oscar Bar og Cafe": ["Oscar Bar Copenhagen"],
    "Cafe Guldhornene": ["Guldhornene"],
    "Den Jyske Ambassade": ["Jyske Ambassade bar"],
    "Det Elektriske Hjørne": ["Elektriske Hjørne"],
    "Funchs Vinstue": ["Funchs"],
    "Tyrolia Bier Klub": ["Tyrolia"],
    "Wall Street Pub": ["Wallstreet Pub"],
    "The Globe": ["The Globe Nørregade", "Globe Irish pub"],
    "The Dubliner": ["Dubliner Copenhagen"],
    "Victoria Pub": ["Victoria Pub København"],
    "Southern Cross Pub": ["Southern Cross Copenhagen"],
    "Kayak Bar": ["Kayak Bar Børskaj"],
    "Kanal Bodega": ["Kanalbodega"],
    "Jailhouse": ["Jailhouse Studiestræde"],
    "Mojo": ["Mojo Løngangstræde"],
    "Wessel Kro": ["Wessel Kro Sværtegade"],
    "Cafe Sommersko": ["Sommersko"],
    "Rust": ["Rust Guldbergsgade"],
    "Nykro": ["Nykroen Vanløse", "Ny Kro"],
    "Snoopy Bodega": ["Snoopy Valby"],
    "Nanok": ["Nanok Valby bar"],
    "Støvlen": ["Støvlen bodega"],
    "Cafe Cire": ["Café Cire"],
    "Anker": ["Anker bodega Amager", "Anker København S"],
    "Jaguar Bodega": ["Jaguar Bodega Amager"],
    "Amager Pub": ["Amager Pub"],
    "Cafe Femøren": ["Femøren cafe"],
    "Børges Bodega": ["Børges Bodega Østerbro"],
    "Hermod Bodega": ["Hermod"],
    "Lumskebuksen": ["Lumskebuksen Østerbro"],
    "Alleenberg": ["Alleenberg Frederiksberg"],
    "Bar Aksel": ["Aksel bar Frederiksberg"],
    "Bartof Station": ["Bartof"],
    "Cafe Moccador": ["Moccador"],
    "Cafe Viggo": ["Viggo Frederiksberg"],
    "Det Gamle Posthus": ["Gamle Posthus Frederiksberg"],
    "Frederik VI": ["Frederik VI bar Frederiksberg"],
    "Hos Robert": ["Hos Robert Frederiksberg"],
    "Barbarian": ["Barbarian Nørrebro"],
    "Bip Bip Bar": ["Bip Bip"],
    "Cafe Castro": ["Café Castro"],
    "Cafe Fuglereden": ["Fuglereden"],
    "Cafe Heimdal": ["Heimdal Nørrebro"],
    "Cafe Klovnen": ["Klovnen"],
    "Cafe Lille Peter": ["Lille Peter"],
    "Cafe Stefanshus": ["Stefanshus"],
    "Franks Kro": ["Frank's Kro", "Franks Kro"],
    "Glentekroen": ["Glente Kroen"],
    "Mimers Bodega": ["Mimers"],
    "Nørre Bodega": ["Nørrebodega"],
    "Temple Bar": ["Temple Bar Nørrebro"],
    "Understellet": ["Understellet Nørrebro"],
    "Axelborg Bodega": ["Axelborg"],
    "Bar 42": ["Bar 42 Vesterbro"],
    "Bar 180": ["Bar 180"],
    "Blomsten": ["Blomsten Vesterbro"],
    "Bryggerens": ["Bryggerens bodega"],
    "Cafe Ludwigsen": ["Ludwigsen"],
    "Cafe Skammekrogen": ["Skammekrogen"],
    "Camping Kødbyen": ["Camping Kødbyen"],
    "Club Mambo": ["Mambo Copenhagen"],
    "Grotten": ["Grotten Vesterbro"],
    "Jernbanecafeen": ["Jernbanecaféen"],
    "Maximum": ["Maximum bar Vesterbro"],
    "The Goat": ["The Goat Copenhagen"],
    "The Scottish Pub": ["Scottish Pub Copenhagen"],
    "Zeppelin Bar": ["Zeppelin Copenhagen"],
    "Restaurant Klubben": ["Klubben Vesterbro"],
    "Alpehytten": ["Alpehytten København"],
    "Bankeråt": ["Bankerat"],
    "Barcelona Bar": ["Barcelona Bar København"],
    "Cafe Katz": ["Café Katz"],
    "Floss": ["Floss bar København"],
    "Hermans Bar": ["Hermans"],
    "Jagtstuen": ["Jagtstuen København"],
    "Masken": ["Masken bar København"],
    "Nørreport Bodega": ["Nørreport Bodega"],
    "Rosengårdens Bodega": ["Rosengården bodega"],
}

AREA_WORDS = {
    "k": "København K",
    "v": "København V",
    "n": "Nørrebro",
    "s": "Amager",
    "o": "Østerbro",
    "frb": "Frederiksberg",
    "val": "Valby",
}

STOP = {
    "bar", "pub", "cafe", "bodega", "kro", "restaurant", "cph", "copenhagen",
    "kobenhavn", "koebenhavn", "the", "and", "og", "hotel", "hostel",
    "karaokebar", "karaoke", "foreningen", "inn", "moving", "music", "house",
    "next", "paa", "i",
}

UA = "j-day-cph/1.0 (one-night personal map for J-dag; contact: adamnagy.dev@gmail.com)"


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s):
    s = strip_accents(s or "")
    s = s.lower().replace("&", " and ")
    s = s.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return [t for t in norm(s).split() if t not in STOP and len(t) > 1]


def slugify(name):
    s = norm(name).replace(" ", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def score_name(query, candidate):
    qn, cn = norm(query), norm(candidate)
    if not qn or not cn:
        return 0.0
    if qn == cn:
        return 1.0
    qt, ct = tokens(query), tokens(candidate)
    ratio = SequenceMatcher(None, qn, cn).ratio()
    if qn in cn or cn in qn:
        ratio = max(ratio, 0.86)
    if qt and ct:
        qset, cset = set(qt), set(ct)
        inter = len(qset & cset)
        if inter:
            cover = inter / len(qset)
            prec = inter / len(cset)
            token_score = 0.65 * cover + 0.35 * prec
            # Numbers are identity: Bar 42 must not match Bar 180.
            qnums = set(re.findall(r"\d+", qn))
            cnums = set(re.findall(r"\d+", cn))
            if qnums != cnums:
                token_score -= 0.45
            return max(ratio, token_score)
    return ratio * 0.92


def in_bbox(lat, lng, box):
    return box[0] <= lat <= box[2] and box[1] <= lng <= box[3]


def http_json(url, data=None, timeout=40, raw=False):
    cmd = ["curl", "-fsS", "--max-time", str(timeout), "-A", UA, "-H", "Accept: application/json"]
    if data is not None:
        if isinstance(data, dict):
            for key, value in data.items():
                cmd.extend(["--data-urlencode", f"{key}={value}"])
        else:
            cmd.extend(["--data-binary", data if isinstance(data, str) else data.decode()])
    cmd.append(url)
    raw_out = subprocess.check_output(cmd, timeout=timeout + 10)
    return json.loads(raw_out.decode())


def load_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))


def overpass():
    query = """
[out:json][timeout:90];
(
  nwr["amenity"~"bar|pub|biergarten|nightclub|cafe|restaurant|fast_food|community_centre|arts_centre|events_venue"](55.60,12.44,55.74,12.68);
  nwr["tourism"~"hostel|hotel|apartment|guest_house"](55.60,12.44,55.74,12.68);
  nwr["name"~"bodega|kro|pub",i](55.60,12.44,55.74,12.68);
);
out center tags;
"""
    urls = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    last = None
    for url in urls:
        try:
            print(f"overpass {url}", flush=True)
            data = http_json(url, data={"data": query}, timeout=120)
            print(f"overpass elements {len(data.get('elements', []))}", flush=True)
            return data.get("elements", [])
        except Exception as exc:
            last = exc
            print(f"overpass failed: {exc}", flush=True)
    raise SystemExit(f"overpass unavailable: {last}")


def element_point(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center") or {}
    if "lat" in center:
        return center["lat"], center["lon"]
    return None


def element_names(el):
    tags = el.get("tags") or {}
    names = []
    for key in ("name", "alt_name", "official_name", "short_name", "old_name"):
        if tags.get(key):
            names.extend(part.strip() for part in re.split(r"[;|]", tags[key]) if part.strip())
    return names


def element_address(tags):
    street = tags.get("addr:street") or ""
    num = tags.get("addr:housenumber") or ""
    post = tags.get("addr:postcode") or ""
    city = tags.get("addr:city") or tags.get("addr:suburb") or ""
    line = " ".join(p for p in (street, num) if p).strip()
    tail = " ".join(p for p in (post, city) if p).strip()
    if line and tail:
        return f"{line}, {tail}"
    return line or tail or ""


def amenity_bonus(tags):
    amenity = (tags.get("amenity") or tags.get("tourism") or "").lower()
    if amenity in {"bar", "pub", "biergarten", "nightclub"}:
        return 0.04
    if amenity in {"cafe", "restaurant", "hostel", "hotel"}:
        return 0.02
    return 0.0


def best_osm(name, area, elements, queries):
    box = BBOX[area]
    best = None
    for el in elements:
        point = element_point(el)
        if not point:
            continue
        lat, lng = point
        if not in_bbox(lat, lng, CITY_BBOX):
            continue
        tags = el.get("tags") or {}
        names = element_names(el)
        if not names:
            continue
        local = in_bbox(lat, lng, box)
        top = 0
        matched = names[0]
        for q in queries:
            for candidate in names:
                s = score_name(q, candidate)
                if s > top:
                    top = s
                    matched = candidate
        if top <= 0:
            continue
        top += amenity_bonus(tags)
        if not local:
            top -= 0.12
        # Generic one-token names must sit in the right district.
        if len(tokens(name)) <= 1 and not local:
            top -= 0.2
        if best is None or top > best[0]:
            best = (top, lat, lng, matched, el, local)
    return best


def photon_search(query, area, cache):
    key = "photon:" + query + ":" + area
    if key in cache:
        return cache[key]
    lat, lng = CENTER[area]
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({
        "q": query,
        "limit": 6,
        "lat": lat,
        "lon": lng,
        "lang": "en",
    })
    try:
        data = http_json(url, timeout=25)
    except Exception as exc:
        print(f"  photon error {exc}", flush=True)
        cache[key] = []
        return []
    cache[key] = data.get("features") or []
    time.sleep(0.35)
    return cache[key]


def nominatim_search(query, cache):
    key = "nominatim:" + query
    if key in cache:
        return cache[key]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "dk",
        "addressdetails": 1,
    })
    try:
        data = http_json(url, timeout=30)
    except Exception as exc:
        print(f"  nominatim error {exc}", flush=True)
        data = []
    cache[key] = data
    time.sleep(1.1)
    return data


def from_photon(name, area, cache, queries):
    box = BBOX[area]
    best = None
    for q in queries[:4]:
        for feature in photon_search(q + ", Copenhagen", area, cache):
            props = feature.get("properties") or {}
            coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
            lon, lat = coords[0], coords[1]
            if lat is None or not in_bbox(lat, lon, CITY_BBOX):
                continue
            candidate = props.get("name") or ""
            s = score_name(q, candidate) if candidate else 0
            if not candidate and props.get("street"):
                s = score_name(q, props.get("street")) * 0.7
            if props.get("osm_key") in {"highway", "place"} and props.get("osm_value") in {"city", "suburb", "residential", "tertiary"}:
                s -= 0.3
            if not in_bbox(lat, lon, box):
                s -= 0.12
            if best is None or s > best[0]:
                street = props.get("street") or ""
                num = props.get("housenumber") or ""
                post = props.get("postcode") or ""
                city = props.get("city") or props.get("district") or ""
                line = " ".join(p for p in (street, num) if p)
                tail = " ".join(p for p in (post, city) if p)
                address = ", ".join(p for p in (line, tail) if p)
                best = (s, lat, lon, candidate or q, address, f"{props.get('osm_type')}/{props.get('osm_id')}", props.get("osm_value") or "")
        if best and best[0] >= 0.9:
            break
    return best


def from_nominatim(name, area, cache, queries):
    box = BBOX[area]
    best = None
    for q in queries[:3]:
        for item in nominatim_search(q + ", København", cache):
            try:
                lat, lon = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not in_bbox(lat, lon, CITY_BBOX):
                continue
            candidate = item.get("name") or ""
            s = score_name(q, candidate) if candidate else 0.45
            klass = item.get("category") or item.get("class") or ""
            if klass in {"highway", "boundary"}:
                continue
            if klass == "place" and item.get("type") in {"city", "suburb", "neighbourhood"}:
                continue
            if not in_bbox(lat, lon, box):
                s -= 0.12
            address = item.get("display_name") or ""
            # Keep the address short.
            parts = [p.strip() for p in address.split(",")]
            address = ", ".join(parts[:3])
            if best is None or s > best[0]:
                best = (s, lat, lon, candidate or q, address, str(item.get("osm_id") or ""), klass)
        if best and best[0] >= 0.9:
            break
    return best


def queries_for(name, area):
    seen = []
    for q in [name, *HINTS.get(name, [])]:
        q = q.strip()
        if q and q not in seen:
            seen.append(q)
    # A cleaner variant without the trailing disambiguator after an en dash.
    head = re.split(r"\s+[–—-]\s+", name)[0].strip()
    if head and head not in seen:
        seen.append(head)
    seen.append(f"{head or name} {AREA_WORDS[area]}")
    return seen


def main():
    cache = load_cache()
    elements = None
    dump = Path("/tmp/overpass-jday.json")
    if dump.exists():
        elements = json.loads(dump.read_text()).get("elements", [])
        print(f"loaded dump {len(elements)}", flush=True)
    if not elements:
        elements = cache.get("__overpass__")
    if not elements:
        elements = overpass()
        cache["__overpass__"] = [
            {
                "type": el.get("type"),
                "id": el.get("id"),
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "center": el.get("center"),
                "tags": el.get("tags"),
            }
            for el in elements
        ]
        save_cache(cache)
    else:
        print(f"cached overpass {len(elements)}", flush=True)

    pubs = []
    used = {}
    for area, name in PUBS:
        qs = queries_for(name, area)
        osm = best_osm(name, area, elements, qs)
        record = {
            "id": slugify(name),
            "name": name,
            "area": area,
            "areaLabel": AREA_LABEL[area],
            "areaShort": AREA_SHORT[area],
        }
        chosen = None
        if osm and osm[0] >= 0.78:
            score, lat, lng, matched, el, local = osm
            tags = el.get("tags") or {}
            chosen = {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "address": element_address(tags),
                "matchedName": matched,
                "source": "osm",
                "confidence": round(score, 3),
                "osmId": f"{el.get('type')}/{el.get('id')}",
                "inArea": local,
                "website": tags.get("website") or tags.get("contact:website") or "",
            }
        else:
            photon = from_photon(name, area, cache, qs)
            save_cache(cache)
            if photon and photon[0] >= 0.8:
                score, lat, lng, matched, address, osm_id, kind = photon
                chosen = {
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "address": address,
                    "matchedName": matched,
                    "source": "photon",
                    "confidence": round(score, 3),
                    "osmId": osm_id,
                    "inArea": in_bbox(lat, lng, BBOX[area]),
                    "website": "",
                    "kind": kind,
                }
            else:
                nomi = from_nominatim(name, area, cache, qs)
                save_cache(cache)
                if nomi and nomi[0] >= 0.78:
                    score, lat, lng, matched, address, osm_id, kind = nomi
                    chosen = {
                        "lat": round(lat, 6),
                        "lng": round(lng, 6),
                        "address": address,
                        "matchedName": matched,
                        "source": "nominatim",
                        "confidence": round(score, 3),
                        "osmId": osm_id,
                        "inArea": in_bbox(lat, lng, BBOX[area]),
                        "website": "",
                        "kind": kind,
                    }
                elif osm and osm[0] >= 0.7:
                    score, lat, lng, matched, el, local = osm
                    tags = el.get("tags") or {}
                    chosen = {
                        "lat": round(lat, 6),
                        "lng": round(lng, 6),
                        "address": element_address(tags),
                        "matchedName": matched,
                        "source": "osm-weak",
                        "confidence": round(score, 3),
                        "osmId": f"{el.get('type')}/{el.get('id')}",
                        "inArea": local,
                        "website": tags.get("website") or "",
                    }
        if chosen:
            record.update(chosen)
            prev = used.get(chosen["osmId"])
            if prev and chosen.get("osmId"):
                record["sharedPin"] = prev
            else:
                used[chosen.get("osmId") or record["id"]] = name
            flag = "" if chosen["confidence"] >= 0.9 and chosen.get("inArea", True) else "  CHECK"
            print(f"{chosen['confidence']:.2f} {name} -> {chosen['matchedName']} | {chosen.get('address','')}{flag}", flush=True)
        else:
            record["lat"] = None
            record["lng"] = None
            record["confidence"] = 0
            record["source"] = "unmatched"
            print(f"MISS {name}", flush=True)
        record["googleQuery"] = f"{name}, {AREA_LABEL[area]}, Danmark"
        pubs.append(record)

    # Ensure unique ids.
    seen = {}
    for pub in pubs:
        base = pub["id"]
        if base in seen:
            pub["id"] = f"{base}-{pub['area']}"
        seen[pub["id"]] = True

    payload = {
        "event": "J-dag",
        "city": "Copenhagen",
        "release": "2026-11-06T20:59:00+01:00",
        "source": "https://migogkbh.dk/oel-og-nisser-paa-j-dag-i-koebenhavn/",
        "sourceNote": "Bar list published by migogkbh.dk on 3 November 2026. Pins are matched to OpenStreetMap and can sit a door or two off.",
        "pubs": pubs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    matched = sum(1 for p in pubs if p.get("lat"))
    print(f"\n{matched}/{len(pubs)} pinned -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
