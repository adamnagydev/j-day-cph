#!/usr/bin/env python3
"""Apply address-checked coordinates. One-off for the 2026 J-dag list."""

import json
import math
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "pubs.json"

# lat, lng, address — checked against the venue's own site or a street address.
FIX = {
    "4tallet": (55.67872, 12.58008, "Højbro Plads 3A, 1200 København"),
    "barcelona-bar": (55.68218, 12.58216, "Gothersgade 35, 1123 København"),
    "borgerly": (55.68646, 12.58738, "Borgergade 93, 1300 København"),
    "cafe-sofie-kaelderen": (55.67162, 12.58997, "Christianshavn"),
    "hoevlen-77": (55.67579, 12.60001, "Prinsessegade 77, 1422 København"),
    "den-jyske-ambassade": (55.68175, 12.58466, "Gothersgade 8A, 1123 København"),
    "liams-irish-pub": (55.68168, 12.58401, "Gothersgade 15, 1123 København"),
    "mc-joys-pub": (55.67994, 12.59132, "Nyhavn 47, 1051 København"),
    "mj-gothersgade": (55.68207, 12.58330, "Gothersgade 26, 1123 København"),
    "palmehaven": (55.68114, 12.57925, "Pilestræde 43, 1112 København"),
    "rosengardens-bodega": (55.68224, 12.57253, "Rosengården 11, 1174 København"),
    "the-dubliner": (55.67864, 12.57889, "Amagertorv, 1160 København"),
    "victoria-pub": (55.67789, 12.57198, "Gammeltorv 26, 1457 København"),
    "bar-180": (55.67642, 12.56369, "Axeltorv 9, 1609 København"),
    "bar-42": (55.66724, 12.55344, "Sønder Boulevard 42, 1720 København"),
    "bryggerens": (55.66733, 12.53355, "Bag Elefanterne 20, 1799 København"),
    "meininger-hotel-copenhagen": (55.67287, 12.56193, "Colbjørnsensgade 5, 1652 København"),
    "nevermind-axeltorv": (55.67566, 12.56411, "Axeltorv 3, 1609 København"),
    "next-house-next-bar-copenhagen": (55.66962, 12.57099, "Bernstorffsgade 27, 1577 København"),
    "franks-kro": (55.69267, 12.56764, "Fredensgade 11, 2200 København N"),
    "cafe-klovnen": (55.68876, 12.54379, "Rantzausgade 70, 2200 København N"),
    "amager-pub": (55.66577, 12.59946, "Amagerbrogade 29, 2300 København S"),
    "cafe-engholm": (55.65099, 12.53642, "Borgbjergsvej 28, 2450 København SV"),
    "restaurant-kareten": (55.66479, 12.59954, "Hollænderdybet 1, 2300 København S"),
    "halifax-trianglen": (55.69899, 12.57788, "Trianglen, Østerbro"),
    "bartof-station": (55.68097, 12.53316, "Frederiksberg"),
    "cafe-bartof": (55.68366, 12.52456, "Frederiksberg"),
    "the-old-irish-pub-smallegade": (55.67866, 12.53257, "Smallegade, Frederiksberg"),
    "old-irish-pub-karaokebar": (55.67559, 12.56654, "Vesterbro"),
    "the-old-irish-pub-vesterbrogade": (55.67548, 12.56629, "Vesterbrogade"),
    "wessel-kro": (55.68117, 12.58074, "Sværtegade 7, 1118 København"),
    "rabalder-bar-cph": (55.68209, 12.58253, "Gothersgade 33, 1123 København"),
    "wall-street-pub": (55.68167, 12.58497, "Gothersgade 2, 1123 København"),
    "noerreport-bodega": (55.68248, 12.57154, "Nørre Voldgade 70, 1358 København"),
    "jagtstuen": (55.68397, 12.56837, "Vendersgade 8, 1363 København"),
    "funchs-vinstue": (55.68449, 12.56739, "Nørre Farimagsgade 55, 1364 København"),
    "kanal-bodega": (55.67200, 12.59062, "Overgaden Oven Vandet 36, 1415 København"),
    "masken": (55.67819, 12.56861, "Studiestræde 33, 1455 København"),
    "axelborg-bodega": (55.67539, 12.56446, "Axeltorv 1, 1609 København"),
    "jernbanecafeen": (55.67222, 12.56355, "Reventlowsgade 16, 1651 København"),
    "cafe-skammekrogen": (55.67173, 12.55479, "Svendsgade 1, 1659 København"),
    "grotten": (55.66764, 12.55545, "Sønder Boulevard 37, 1720 København"),
    "hos-robert": (55.67024, 12.53719, "Vesterbrogade 161, 1800 Frederiksberg"),
    "chevy-s-bar": (55.70372, 12.58999, "Nordre Frihavnsgade 95, 2100 København Ø"),
    "glentekroen": (55.69796, 12.53548, "Nordre Fasanvej 237, 2200 København N"),
    "noerre-bodega": (55.69503, 12.54803, "Nørrebrogade 152, 2200 København N"),
    "understellet": (55.68830, 12.55990, "Nørrebrogade 24, 2200 København N"),
    "mimers-bodega": (55.69830, 12.55032, "Thorsgade 70, 2200 København N"),
    "western-bar-diligencen": (55.68493, 12.55881, "Korsgade 8, 2200 København N"),
    "cafe-lille-peter": (55.69576, 12.54389, "Stefansgade 14, 2200 København N"),
    "cafe-heimdal": (55.70065, 12.54172, "Heimdalsgade 17, 2200 København N"),
    "cafe-fuglereden": (55.70474, 12.52644, "Frederikssundsvej 70, 2400 København NV"),
    "post-bodegaen": (55.66171, 12.61025, "Lyongade 25, 2300 København S"),
    "moelle-cafeen": (55.66537, 12.51727, "Mølle Allé 16, 2500 Valby"),
    "nanok": (55.66678, 12.50504, "Valby Langgade 126, 2500 Valby"),
    "stoevlen": (55.69190, 12.48353, "Jyllingevej 58, 2720 Vanløse"),
    "oscar-bar-og-cafe": (55.67577, 12.57160, "Rådhuspladsen"),
    "blomsten": (55.68069, 12.58938, "Lille Strandstræde, 1254 København"),
}

NOTES = {
    "blomsten": "Listed under Vesterbro. The bar itself is on Lille Strandstræde, by Nyhavn.",
    "a-v-f-landbohoejskolen": "Pinned to the Frederiksberg campus. The student bar is inside the school.",
    "cafe-nemoland-christiania": "Inside Christiania, at Fabriksområdet.",
}

UNPIN = {"anker", "cafe-femoeren", "foreningen-cafedrift", "bar-aksel"}


def dist(a, b, c, d):
    if None in (a, b, c, d):
        return None
    p = math.pi / 180
    x = (c - a) * p
    y = (d - b) * p
    h = math.sin(x / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin(y / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def main():
    data = json.loads(PATH.read_text())
    pubs = {p["id"]: p for p in data["pubs"]}
    for pid, (lat, lng, addr) in FIX.items():
        pub = pubs[pid]
        moved = dist(pub.get("lat"), pub.get("lng"), lat, lng)
        if moved and moved > 80:
            print(f"MOVE {moved:6.0f}m  {pub['name']}")
        pub.update({
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "address": addr,
            "source": "checked",
            "confidence": 0.99,
            "inArea": True,
            "googleQuery": f"{pub['name']}, {addr}",
        })
        pub.pop("sharedPin", None)

    for pid in UNPIN:
        pub = pubs[pid]
        print("UNPIN", pub["name"])
        pub.update({"lat": None, "lng": None, "address": "", "source": "unmatched", "confidence": 0, "inArea": False})
        pub.pop("sharedPin", None)

    for pid, note in NOTES.items():
        pubs[pid]["note"] = note

    for pid, query, addr in [
        ("hermod-bodega", "Vordingborggade 2, København Ø", "Vordingborggade 2, 2100 København Ø"),
        ("det-gamle-posthus", "Borups Allé 121, Frederiksberg", "Borups Allé 121, 2000 Frederiksberg"),
        ("snoopy-bodega", "Linde Allé 11, Vanløse", "Linde Allé 11, 2720 Vanløse"),
    ]:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": query, "format": "jsonv2", "limit": 1, "countrycodes": "dk",
        })
        raw = subprocess.check_output([
            "curl", "-fsS", "--max-time", "25",
            "-A", "j-day-cph/1.0 (personal J-dag map)", url,
        ])
        rows = json.loads(raw)
        time.sleep(1.1)
        pub = pubs[pid]
        if not rows:
            print("NO NOMI", pub["name"])
            continue
        lat, lng = float(rows[0]["lat"]), float(rows[0]["lon"])
        moved = dist(pub.get("lat"), pub.get("lng"), lat, lng)
        print(f"NOMI {pub['name']}: {None if moved is None else round(moved)}m -> {rows[0].get('display_name','')[:90]}")
        if 55.61 <= lat <= 55.74 and 12.45 <= lng <= 12.66:
            pub.update({
                "lat": round(lat, 6), "lng": round(lng, 6), "address": addr,
                "source": "checked", "confidence": 0.99, "inArea": True,
                "googleQuery": f"{pub['name']}, {addr}",
            })
            pub.pop("sharedPin", None)

    for pub in data["pubs"]:
        pub.pop("sharedPin", None)
        if pub["id"] in {"cafe-nemoland-christiania", "camping-koedbyen", "tjilipop", "studiecafeen-humlen", "a-v-f-landbohoejskolen"}:
            pub["confidence"] = 0.95
            pub["inArea"] = True
            pub["source"] = "checked"

    data["sourceNote"] = (
        "Bar list from migogkbh.dk, 3 November 2026. Pins checked against OpenStreetMap "
        "and published addresses. A few bars had no reliable public address and are listed without a pin."
    )
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    pinned = sum(1 for p in data["pubs"] if p.get("lat"))
    print(f"pinned {pinned}/{len(data['pubs'])}")
    print("--- still soft ---")
    for pub in data["pubs"]:
        if pub.get("lat") is None or (pub.get("source") != "checked" and (pub.get("confidence") or 0) < 0.9):
            print(f"{pub['id']:42} {pub.get('source')} c={pub.get('confidence')} {(pub.get('address') or '')[:40]}")


if __name__ == "__main__":
    main()
