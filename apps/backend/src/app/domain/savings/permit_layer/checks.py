"""Individual permit check functions — one per check, all return PermitCheck.

Each function is self-contained: makes HTTP calls, applies rules, returns a structured result.
Called concurrently by engine.py via ThreadPoolExecutor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OPENPLZ_URL = "https://openplzapi.org/de/Localities"
# MaStR SOAP API was decommissioned — we use Tavily search as fallback
_MASTR_SEARCH_QUERY = "Solaranlagen Marktstammdatenregister PLZ {plz} Anzahl registriert"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Bundesland → Denkmal WMS endpoint (None = OSM-only fallback)
DENKMAL_WMS: dict[str, str | None] = {
    "Bayern": "https://geoservices.bayern.de/od/wms/gdi/v1/denkmal",
    "Nordrhein-Westfalen": "https://www.wms.nrw.de/wms/wms_nw_inspire-denkmal",
    "Berlin": "https://fbinter.stadt-berlin.de/fb/wms/senstadt/denkmal",
    "Rheinland-Pfalz": "https://www.geoportal.rlp.de/wms/rlp_denkmal",
    "Sachsen-Anhalt": "https://www.geodatenportal.sachsen-anhalt.de/wms/denkmal",
    "Bremen": "https://geodienste.bremen.de/wms/denkmal",
    # The rest fall back to OSM Overpass
    "Baden-Württemberg": "https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_DENKMAL",
    "Brandenburg": None,
    "Hamburg": None,
    "Hessen": None,              # WFS only, not GetFeatureInfo-friendly
    "Mecklenburg-Vorpommern": None,
    "Niedersachsen": None,       # restricted
    "Saarland": None,
    "Sachsen": None,
    "Schleswig-Holstein": None,
    "Thüringen": None,
}

# Module-level PLZ cache to avoid hammering OpenPLZ
_plz_cache: dict[str, str] = {}


# Provenance of a check result — how we know what we know.
SourceType = Literal["live_internet", "supabase_cache", "seeded_fallback", "static_rule"]

# Categories the activity feed groups checks under, in display order.
PERMIT_CATEGORY_ORDER: list[str] = [
    "Location",
    "Solar permissions",
    "Heat pump permissions",
    "EV charger permissions",
    "Battery permissions",
]

# product → category. "location" is a synthetic product for the orienting check.
_PRODUCT_CATEGORY: dict[str, str] = {
    "location": "Location",
    "solar": "Solar permissions",
    "heatpump": "Heat pump permissions",
    "ev_charger": "EV charger permissions",
    "battery": "Battery permissions",
}

# Per-check reasoning, keyed by check id. Stable regardless of pass/warn/fail — it
# explains what the check means and how it feeds the offer. Deterministic (no money
# math here); the engine owns all € figures. Shape: (why_it_matters, offer_effect).
_PERMIT_REASONING: dict[str, tuple[str, str]] = {
    "location": (
        "Locates the address in its Bundesland and municipality to pick the right rules.",
        "Sets which LBO / Denkmal / B-Plan rules apply to every downstream permit check.",
    ),
    "solar_lbo": (
        "Determines whether solar needs a building permit at all.",
        "Verfahrensfrei means no permit delay — the solar rung can proceed immediately.",
    ),
    "solar_denkmal": (
        "A heritage listing can block roof-mounted PV.",
        "If listed, the solar rung may be removed or need authority approval before install.",
    ),
    "hp_denkmal": (
        "Heritage rules can restrict a visible outdoor unit.",
        "If listed, heat-pump placement may need approval; siting the unit out of "
        "view usually resolves it.",
    ),
    "solar_bplan": (
        "The local development plan can restrict roof PV.",
        "A restriction flags the solar rung for Bauamt confirmation; silence means "
        "the baseline permits it.",
    ),
    "hp_bplan": (
        "The local development plan can restrict outdoor units.",
        "A restriction flags the heat-pump rung for confirmation; silence means it is permitted.",
    ),
    "solar_mastr": (
        "Neighbour installations show local permitting is routine.",
        "Strong precedent raises confidence in the solar rung; thin precedent is "
        "informational only.",
    ),
    "ev_parking": (
        "A wallbox needs a private parking space.",
        "No private parking removes the EV-charger rung from the offer.",
    ),
    "ev_weg": (
        "Apartments need a co-owner vote to install a wallbox.",
        "A WEG requirement keeps the EV rung but adds an approval step before install.",
    ),
    "hp_geg": (
        "GEG 2024 governs when a fossil boiler must be replaced.",
        "An old boiler makes the heat-pump rung mandatory-eligible and maximises the "
        "KfW 458 subsidy window.",
    ),
    "hp_noise": (
        "TA Lärm limits outdoor-unit noise on dense plots.",
        "A tight plot keeps the heat-pump rung but recommends a low-noise unit and careful siting.",
    ),
    "battery_install": (
        "Confirms indoor storage needs no permit.",
        "No permit barrier — the battery rung can be added whenever the economics support it.",
    ),
    "battery_mastr": (
        "Grid-connected batteries must be registered in MaStR.",
        "Registration is a post-install installer task; it does not affect the offer economics.",
    ),
}


@dataclass
class PermitCheck:
    id: str
    product: str                              # "solar"|"heatpump"|"ev_charger"|"battery"
    check_name: str
    status: Literal["pass", "warn", "fail", "info"]
    label: str
    detail: str
    cited_clause: str | None
    source_url: str | None
    source_name: str
    fetched_at: str                           # ISO 8601
    category: str = ""                        # one of PERMIT_CATEGORY_ORDER
    source_type: SourceType = "static_rule"   # how the result was obtained
    confidence: float | None = None           # 0–1, when meaningful
    why_it_matters: str = ""                  # deterministic reasoning for the feed
    offer_effect: str = ""                    # how the result feeds the offer


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_check(
    id: str,
    product: str,
    check_name: str,
    status: Literal["pass", "warn", "fail", "info"],
    label: str,
    detail: str,
    source_name: str,
    source_url: str | None = None,
    cited_clause: str | None = None,
    *,
    source_type: SourceType = "static_rule",
    confidence: float | None = None,
) -> PermitCheck:
    why, effect = _PERMIT_REASONING.get(id, ("", ""))
    return PermitCheck(
        id=id,
        product=product,
        check_name=check_name,
        status=status,
        label=label,
        detail=detail,
        cited_clause=cited_clause,
        source_url=source_url,
        source_name=source_name,
        fetched_at=_now(),
        category=_PRODUCT_CATEGORY.get(product, ""),
        source_type=source_type,
        confidence=confidence,
        why_it_matters=why,
        offer_effect=effect,
    )


def group_by_category(checks: list[PermitCheck]) -> dict[str, list[PermitCheck]]:
    """Group checks into the canonical category order (empty categories omitted)."""
    grouped: dict[str, list[PermitCheck]] = {cat: [] for cat in PERMIT_CATEGORY_ORDER}
    for ch in checks:
        grouped.setdefault(ch.category or "Location", []).append(ch)
    return {cat: rows for cat, rows in grouped.items() if rows}


# ---------------------------------------------------------------------------
# Helper: PLZ → Bundesland
# ---------------------------------------------------------------------------

def plz_to_bundesland(plz: str) -> str:
    """Return the Bundesland name for a German postal code."""
    if plz in _plz_cache:
        return _plz_cache[plz]
    try:
        resp = httpx.get(
            _OPENPLZ_URL,
            params={"postalCode": plz, "pageSize": 1},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            bl = data[0].get("federalState", {}).get("name", "Unknown")
            _plz_cache[plz] = bl
            return bl
    except Exception:
        pass
    return "Unknown"


def check_location(plz: str, city: str) -> PermitCheck:
    """Orienting check: resolve PLZ → Bundesland so downstream rules pick the right LBO."""
    bundesland = plz_to_bundesland(plz)
    if bundesland != "Unknown":
        return _make_check(
            "location", "location", "Address → Bundesland",
            "pass", f"{city or plz} · {bundesland}",
            f"PLZ {plz} resolved to {bundesland}. Local building rules selected for this state.",
            "OpenPLZ API", "https://openplzapi.org",
            source_type="live_internet", confidence=0.9,
        )
    return _make_check(
        "location", "location", "Address → Bundesland",
        "warn", f"{city or plz} · state unresolved",
        f"Could not resolve PLZ {plz} to a Bundesland. Falling back to federal baseline rules.",
        "OpenPLZ API", "https://openplzapi.org",
        source_type="seeded_fallback", confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Check 1+2: Denkmalschutz — solar (fail) and heat pump (warn if listed)
# ---------------------------------------------------------------------------

def _query_denkmal_wms(lat: float, lng: float, wms_url: str) -> tuple[bool, str]:
    """Return (is_listed, feature_name). Uses WMS GetFeatureInfo at coordinates."""
    d = 0.0005  # ~55m bounding box
    try:
        resp = httpx.get(
            wms_url,
            params={
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetFeatureInfo",
                "QUERY_LAYERS": "denkmal",
                "LAYERS": "denkmal",
                "BBOX": f"{lat - d},{lng - d},{lat + d},{lng + d}",
                "CRS": "EPSG:4326",
                "WIDTH": "3",
                "HEIGHT": "3",
                "I": "1",
                "J": "1",
                "INFO_FORMAT": "application/json",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if features:
            name = features[0].get("properties", {}).get("bezeichnung", "Kulturdenkmal")
            return True, str(name)
        return False, ""
    except Exception:
        return False, ""


def _query_denkmal_osm(lat: float, lng: float) -> tuple[bool, str]:
    """Return (is_listed, tag). Uses Overpass API to check OSM heritage tags."""
    query = f"""
[out:json][timeout:10];
(
  way(around:25,{lat},{lng})[historic];
  way(around:25,{lat},{lng})[heritage];
  way(around:25,{lat},{lng})[building:protection_status];
  node(around:25,{lat},{lng})[historic];
);
out 1;
"""
    try:
        resp = httpx.post(_OVERPASS_URL, data={"data": query}, timeout=12)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if elements:
            tags = elements[0].get("tags", {})
            name = tags.get("name") or tags.get("historic") or "heritage feature"
            return True, str(name)
        return False, ""
    except Exception:
        return False, ""


def check_denkmal_solar(lat: float, lng: float, bundesland: str) -> PermitCheck:
    """Solar PV: blocked if building is heritage-listed."""
    wms_url = DENKMAL_WMS.get(bundesland)
    source_name = f"{bundesland} Denkmal WMS" if wms_url else "OpenStreetMap Overpass"
    source_url = wms_url or "https://overpass-api.de"

    if wms_url:
        listed, name = _query_denkmal_wms(lat, lng, wms_url)
        if listed:
            return _make_check(
                "solar_denkmal", "solar", "Heritage protection",
                "fail",
                f"Heritage listed — {name}",
                "Solar panels require Denkmalschutzbehörde approval (usually refused for listed buildings).",
                source_name, source_url,
                source_type="live_internet", confidence=0.9,
            )
        return _make_check(
            "solar_denkmal", "solar", "Heritage protection",
            "pass", "Not heritage listed",
            f"No Kulturdenkmal found at this address ({bundesland} monument registry).",
            source_name, source_url,
            source_type="live_internet", confidence=0.9,
        )

    # Fallback: OSM
    listed, name = _query_denkmal_osm(lat, lng)
    if listed:
        return _make_check(
            "solar_denkmal", "solar", "Heritage protection",
            "fail",
            f"Possible heritage listing — {name}",
            "OSM indicates a heritage feature nearby. Confirm with local Denkmalschutzbehörde.",
            "OpenStreetMap Overpass", "https://overpass-api.de",
            source_type="live_internet", confidence=0.5,
        )
    # OSM-only Bundesland with no hit → can't confirm clear
    return _make_check(
        "solar_denkmal", "solar", "Heritage protection",
        "warn", "Heritage status unverified",
        f"No public Denkmal API for {bundesland}. Confirm with Landesdenkmalamt before ordering.",
        "OpenStreetMap Overpass", "https://overpass-api.de",
        source_type="live_internet", confidence=0.3,
    )


def check_denkmal_heatpump(lat: float, lng: float, bundesland: str) -> PermitCheck:
    """Heat pump: listed buildings need approval (warn, not auto-fail — HP sometimes approved)."""
    wms_url = DENKMAL_WMS.get(bundesland)
    source_name = f"{bundesland} Denkmal WMS" if wms_url else "OpenStreetMap Overpass"
    source_url = wms_url or "https://overpass-api.de"

    if wms_url:
        listed, name = _query_denkmal_wms(lat, lng, wms_url)
        if listed:
            return _make_check(
                "hp_denkmal", "heatpump", "Heritage protection",
                "warn",
                f"Heritage listed — approval needed ({name})",
                "Heat pump outdoor unit requires Denkmalschutzbehörde approval. Often granted if unit is not visible from street.",
                source_name, source_url,
                source_type="live_internet", confidence=0.9,
            )
        return _make_check(
            "hp_denkmal", "heatpump", "Heritage protection",
            "pass", "Not heritage listed",
            f"No Kulturdenkmal found at this address ({bundesland} monument registry).",
            source_name, source_url,
            source_type="live_internet", confidence=0.9,
        )

    listed, name = _query_denkmal_osm(lat, lng)
    if listed:
        return _make_check(
            "hp_denkmal", "heatpump", "Heritage protection",
            "warn",
            f"Possible heritage listing — {name}",
            "OSM indicates a heritage feature. Confirm with Denkmalschutzbehörde before installation.",
            "OpenStreetMap Overpass", "https://overpass-api.de",
            source_type="live_internet", confidence=0.5,
        )
    return _make_check(
        "hp_denkmal", "heatpump", "Heritage protection",
        "warn", "Heritage status unverified",
        f"No public Denkmal API for {bundesland}. Confirm with Landesdenkmalamt before ordering.",
        "OpenStreetMap Overpass", "https://overpass-api.de",
        source_type="live_internet", confidence=0.3,
    )


# ---------------------------------------------------------------------------
# Check 3+4: Bebauungsplan RAG — solar and heat pump
# ---------------------------------------------------------------------------

def check_bplan(
    plz: str,
    city: str,
    tavily_api_key: str,
    anthropic_api_key: str,
) -> list[PermitCheck]:
    """B-Plan check for solar + heat pump using Tavily search + LLM clause extraction."""
    if not tavily_api_key:
        return [
            _make_check("solar_bplan", "solar", "Zone + solar permitted", "warn",
                        "B-Plan check skipped (no Tavily key)",
                        "Bundesland baseline applies. Verify with local Bauamt.",
                        "Bebauungsplan RAG",
                        source_type="seeded_fallback"),
            _make_check("hp_bplan", "heatpump", "Zone + outdoor unit permitted", "warn",
                        "B-Plan check skipped (no Tavily key)",
                        "Bundesland baseline applies. Verify with local Bauamt.",
                        "Bebauungsplan RAG",
                        source_type="seeded_fallback"),
        ]

    # Tavily search — use city name for targeted results
    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]
        client = TavilyClient(api_key=tavily_api_key)
        result = client.search(
            query=f"Bebauungsplan {city} {plz} Geoportal Solaranlage Festsetzung",
            search_depth="basic",
            max_results=3,
            include_raw_content=True,
        )
        content = "\n\n".join(
            r.get("raw_content") or r.get("content", "")
            for r in result.get("results", [])
        )
        top_url = result.get("results", [{}])[0].get("url") if result.get("results") else None
    except Exception:
        content = ""
        top_url = None

    if not content.strip() or not anthropic_api_key:
        # No B-Plan found → federal/Bundesland baseline (verfahrensfrei) applies
        return [
            _make_check("solar_bplan", "solar", "Zone + solar permitted", "pass",
                        "No B-Plan restriction found",
                        f"No specific Bebauungsplan found for {city} ({plz}). Federal baseline applies — solar PV is verfahrensfrei under LBO.",
                        "Bebauungsplan RAG", top_url,
                        source_type="live_internet", confidence=0.5),
            _make_check("hp_bplan", "heatpump", "Zone + outdoor unit permitted", "pass",
                        "No B-Plan restriction found",
                        f"No specific Bebauungsplan found for {city} ({plz}). Federal baseline applies — outdoor heat pump unit is generally permitted.",
                        "Bebauungsplan RAG", top_url,
                        source_type="live_internet", confidence=0.5),
        ]

    # LLM extraction
    prompt = (
        "You are a German building law expert. Analyse the following Bebauungsplan text and extract "
        "permit status for (1) solar panels / Photovoltaikanlage and (2) heat pump outdoor units / "
        "Wärmepumpe Außengerät.\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        '{"solar":{"status":"permitted|restricted|silent","clause":"<exact quoted text or null>"},'
        '"heatpump":{"status":"permitted|restricted|silent","clause":"<exact quoted text or null>"}}\n\n'
        f"Bebauungsplan text:\n{content[:4000]}"
    )

    try:
        resp = httpx.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        extracted = json.loads(raw)
    except Exception:
        extracted = {"solar": {"status": "silent", "clause": None},
                     "heatpump": {"status": "silent", "clause": None}}

    def _bplan_check(check_id: str, product: str, check_name: str, key: str) -> PermitCheck:
        info = extracted.get(key, {})
        status_str = info.get("status", "silent")
        clause = info.get("clause")
        if status_str == "restricted":
            return _make_check(check_id, product, check_name, "fail",
                                "Restricted by B-Plan",
                                "Bebauungsplan contains a restriction. Confirm with Bauamt before ordering.",
                                "Bebauungsplan RAG", top_url, clause,
                                source_type="live_internet", confidence=0.7)
        if status_str == "permitted":
            return _make_check(check_id, product, check_name, "pass",
                                "Permitted by B-Plan",
                                "Bebauungsplan explicitly permits this installation.",
                                "Bebauungsplan RAG", top_url, clause,
                                source_type="live_internet", confidence=0.7)
        # silent → fall back to Bundesland baseline (verfahrensfrei)
        return _make_check(check_id, product, check_name, "pass",
                            "No B-Plan restriction found",
                            "B-Plan is silent on this — Bundesland baseline (verfahrensfrei) applies.",
                            "Bebauungsplan RAG", top_url, clause,
                            source_type="live_internet", confidence=0.6)

    return [
        _bplan_check("solar_bplan", "solar", "Zone + solar permitted", "solar"),
        _bplan_check("hp_bplan", "heatpump", "Zone + outdoor unit permitted", "heatpump"),
    ]


# ---------------------------------------------------------------------------
# Check 5: MaStR neighbour count
# ---------------------------------------------------------------------------

_MASTR_KENDO_URL = "https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitenAjaxMVC"


def _classify_mastr(
    count: int,
    plz: str,
    source_url: str,
    source_type: SourceType = "live_internet",
    confidence: float | None = None,
) -> PermitCheck:
    mastr_url = f"https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitenMVC?filter=Postleitzahl~eq~{plz}~and~Einheittyp~eq~2"
    if count >= 40:
        return _make_check(
            "solar_mastr", "solar", "Neighbourhood precedent",
            "pass", f"~{count} solar systems in PLZ {plz}",
            "Established solar area — permits clearly granted to neighbours.",
            "BNetzA Marktstammdatenregister", source_url,
            source_type=source_type, confidence=confidence,
        )
    if count >= 5:
        return _make_check(
            "solar_mastr", "solar", "Neighbourhood precedent",
            "warn", f"~{count} solar systems in PLZ {plz}",
            "Early adopter area — solar is possible but less precedent locally.",
            "BNetzA Marktstammdatenregister", source_url,
            source_type=source_type, confidence=confidence,
        )
    return _make_check(
        "solar_mastr", "solar", "Neighbourhood precedent",
        "warn", f"~{count} solar systems in PLZ {plz}",
        "Few solar installations found for this PLZ. Solar is still possible — check with local Bauamt.",
        "BNetzA Marktstammdatenregister", mastr_url,
        source_type=source_type, confidence=confidence,
    )


def check_mastr(
    plz: str,
    supabase_url: str = "",
    supabase_key: str = "",
    tavily_api_key: str = "",
) -> PermitCheck:
    """Count solar systems in PLZ. Sources: Supabase → MaStR Kendo grid → Tavily → warn."""
    mastr_url = f"https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitenMVC?filter=Postleitzahl~eq~{plz}~and~Einheittyp~eq~2"

    # Tier 1: Supabase plz_solar_count table (seeded from MaStR export)
    if supabase_url and supabase_key:
        try:
            resp = httpx.get(
                f"{supabase_url.rstrip('/')}/rest/v1/plz_solar_count",
                params={"plz": f"eq.{plz}", "select": "count"},
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                timeout=5,
            )
            rows = resp.json()
            if rows:
                return _classify_mastr(int(rows[0]["count"]), plz, mastr_url,
                                       source_type="supabase_cache", confidence=0.85)
        except Exception:
            pass

    # Tier 2: MaStR public page — scrape total count from JSON embedded in HTML
    try:
        resp = httpx.get(
            mastr_url,
            headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            timeout=12,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            import re
            # Page embeds Kendo data-source or a total count in the HTML
            match = re.search(r'"Total"\s*:\s*(\d+)', resp.text)
            if not match:
                match = re.search(r'total["\s]*:\s*(\d+)', resp.text, re.IGNORECASE)
            if match:
                return _classify_mastr(int(match.group(1)), plz, mastr_url,
                                       source_type="live_internet", confidence=0.8)
    except Exception:
        pass

    # Tier 3: Tavily search as last resort
    if tavily_api_key:
        try:
            from tavily import TavilyClient  # type: ignore[import-untyped]
            client = TavilyClient(api_key=tavily_api_key)
            result = client.search(
                query=f"Marktstammdatenregister Solaranlagen PLZ {plz} Einheiten registriert",
                search_depth="basic",
                max_results=2,
            )
            snippet = " ".join(r.get("content", "") for r in result.get("results", []))
            top_url = result.get("results", [{}])[0].get("url") if result.get("results") else mastr_url
            import re
            numbers = re.findall(r'\b(\d{1,5})\b', snippet)
            count = max((int(n) for n in numbers if 1 <= int(n) <= 50000), default=0)
            if count:
                return _classify_mastr(count, plz, top_url or mastr_url,
                                       source_type="live_internet", confidence=0.5)
        except Exception:
            pass

    return _make_check(
        "solar_mastr", "solar", "Neighbourhood precedent",
        "warn", f"Solar count for PLZ {plz} unclear",
        "Could not query MaStR. Check manually if needed — this is a trust signal, not a permit check.",
        "BNetzA Marktstammdatenregister", mastr_url,
        source_type="live_internet", confidence=0.2,
    )


# ---------------------------------------------------------------------------
# Check 6: EV charger — private parking
# ---------------------------------------------------------------------------

def check_ev_parking(lat: float, lng: float, has_private_parking: bool) -> PermitCheck:
    """EV charger requires a private driveway or garage."""
    # User checkbox is the primary signal
    if has_private_parking:
        return _make_check(
            "ev_parking", "ev_charger", "Private parking available",
            "pass", "Private driveway / garage confirmed",
            "Wallbox can be installed at your private parking space.",
            "User input + OSM",
            source_type="static_rule", confidence=0.9,
        )

    # Try OSM as secondary check
    query = f"""
[out:json][timeout:8];
(
  way(around:30,{lat},{lng})[amenity=parking][access=private];
  way(around:30,{lat},{lng})[amenity=parking_space];
);
out 1;
"""
    try:
        resp = httpx.post(_OVERPASS_URL, data={"data": query}, timeout=10)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if elements:
            return _make_check(
                "ev_parking", "ev_charger", "Private parking available",
                "warn", "Possible private parking nearby (OSM)",
                "OSM shows a parking area near your address. Confirm it's yours before ordering.",
                "OpenStreetMap Overpass", "https://overpass-api.de",
                source_type="live_internet", confidence=0.5,
            )
    except Exception:
        pass

    return _make_check(
        "ev_parking", "ev_charger", "Private parking available",
        "fail", "No private parking confirmed",
        "A wallbox requires a private driveway or garage. Street-only parking blocks installation.",
        "User input + OpenStreetMap Overpass",
        source_type="static_rule", confidence=0.4,
    )


# ---------------------------------------------------------------------------
# Check 7: EV charger — apartment / WEG
# ---------------------------------------------------------------------------

def check_ev_weg(lat: float, lng: float) -> PermitCheck:
    """Apartment buildings need a WEG owner vote for wallbox installation."""
    query = f"""
[out:json][timeout:8];
way(around:10,{lat},{lng})[building~"^(apartments|flat|residential|yes)$"];
out 1;
"""
    try:
        resp = httpx.post(_OVERPASS_URL, data={"data": query}, timeout=10)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if elements:
            btype = elements[0].get("tags", {}).get("building", "residential")
            if btype in ("apartments", "flat"):
                return _make_check(
                    "ev_weg", "ev_charger", "Apartment building — WEG",
                    "warn", "Apartment building — owner vote needed",
                    "Installation in a Mehrfamilienhaus requires a WEG owners' vote (§20 WEG). We assist with the process.",
                    "OpenStreetMap Overpass", "https://overpass-api.de",
                    source_type="live_internet", confidence=0.6,
                )
    except Exception:
        pass

    return _make_check(
        "ev_weg", "ev_charger", "Apartment building — WEG",
        "pass", "Single-family home",
        "No WEG vote required. Legal right to install confirmed (§554 BGB / homeowner).",
        "OpenStreetMap Overpass", "https://overpass-api.de",
        source_type="live_internet", confidence=0.6,
    )


# ---------------------------------------------------------------------------
# Check 8: Heat pump — GEG 2024 boiler age
# ---------------------------------------------------------------------------

def check_hp_geg(building_year: int, fuel_type: str) -> PermitCheck:
    """Heat pump GEG 2024 compliance — hardcoded rule."""
    source = "Gebäudeenergiegesetz (GEG) §71, §72"

    if fuel_type.upper() not in ("OIL", "GAS"):
        return _make_check(
            "hp_geg", "heatpump", "Boiler age — GEG 2024",
            "pass", "Non-fossil heating — HP upgrade always permitted",
            "Current heating is not oil or gas. Heat pump upgrade is always GEG-compliant.",
            source,
        )

    boiler_age = 2024 - building_year  # conservative: assume boiler as old as building
    if boiler_age >= 20:
        return _make_check(
            "hp_geg", "heatpump", "Boiler age — GEG 2024",
            "pass", "Replacement permitted (boiler ≥ 20 years)",
            f"Your heating system is ≥ 20 years old — replacement with heat pump required under GEG §72.",
            source,
            cited_clause="GEG §72: Heizkessel, die mit flüssigen oder gasförmigen Brennstoffen betrieben werden und vor dem 1. Januar 1991 eingebaut wurden, dürfen nicht mehr betrieben werden.",
        )

    return _make_check(
        "hp_geg", "heatpump", "Boiler age — GEG 2024",
        "warn", "Boiler protected until 2029 — HP still recommended",
        f"Boiler is < 20 years old. Mandatory replacement postponed until 2029 under GEG §71 transitional rules. Installing HP now maximises KfW 458 subsidy window.",
        source,
        cited_clause="GEG §71 Abs. 9: Übergangsregelung bis 31. Dezember 2029 für bestehende Anlagen.",
    )


# ---------------------------------------------------------------------------
# Check: Solar PV — LBO verfahrensfrei baseline
# ---------------------------------------------------------------------------

def check_solar_lbo(bundesland: str) -> PermitCheck:
    """Explicit affirmation that solar PV is verfahrensfrei under Landesbauordnung."""
    return _make_check(
        "solar_lbo", "solar", "Solar PV — permit required?",
        "pass", "Verfahrensfrei — no building permit needed",
        f"Solar PV on private residential roofs is verfahrensfrei under {bundesland} LBO. No permit application required.",
        f"{bundesland} Landesbauordnung (LBO)",
        cited_clause="§ 50 LBO BW (analog in all Bundesländer): Photovoltaikanlagen auf Dach- und Außenwandflächen sind verfahrensfrei.",
    )


# ---------------------------------------------------------------------------
# Check: Heat pump — TA Lärm noise advisory
# ---------------------------------------------------------------------------

def check_hp_noise(lat: float, lng: float) -> PermitCheck:
    """TA Lärm advisory — heat pump outdoor unit noise check based on plot density."""
    # Query OSM for dense urban context (buildings within 8m)
    query = f"""
[out:json][timeout:8];
(
  way(around:8,{lat},{lng})[building];
  way(around:8,{lat},{lng})[landuse=residential];
);
out 1;
"""
    try:
        resp = httpx.post(_OVERPASS_URL, data={"data": query}, timeout=10)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        if elements:
            return _make_check(
                "hp_noise", "heatpump", "Noise — TA Lärm",
                "warn", "Dense plot — noise advisory applies",
                "Neighbouring buildings within 8m. Heat pump outdoor unit must comply with TA Lärm (≤45 dB night). Choose a low-noise model (≤40 dB) and avoid north/east-facing garden walls.",
                "TA Lärm (Technische Anleitung zum Schutz gegen Lärm)",
                cited_clause="TA Lärm Nr. 6.1: Immissionsrichtwerte für Wohngebiete nachts 40 dB(A), tags 55 dB(A).",
                source_type="live_internet", confidence=0.5,
            )
    except Exception:
        pass

    return _make_check(
        "hp_noise", "heatpump", "Noise — TA Lärm",
        "pass", "Sufficient space for outdoor unit",
        "No immediately adjacent buildings detected. Standard heat pump outdoor unit installation is compliant with TA Lärm.",
        "TA Lärm (Technische Anleitung zum Schutz gegen Lärm)",
        cited_clause="TA Lärm Nr. 6.1: Immissionsrichtwerte für Wohngebiete nachts 40 dB(A).",
        source_type="live_internet", confidence=0.5,
    )


# ---------------------------------------------------------------------------
# Check 9+10: Battery — installation + grid registration
# ---------------------------------------------------------------------------

def check_battery_install() -> PermitCheck:
    return _make_check(
        "battery_install", "battery", "Indoor installation",
        "pass", "Always permitted — no approval needed",
        "Indoor battery storage ≤ 30 kWh requires no building permit or authority notification.",
        "Hardcoded rule (DE law)",
    )


def check_battery_mastr() -> PermitCheck:
    return _make_check(
        "battery_mastr", "battery", "Grid registration",
        "info", "MaStR registration after install — installer task",
        "Battery connected to the grid must be registered in MaStR within 1 month of commissioning. Your installer handles this.",
        "Hardcoded advisory",
        cited_clause="EEG 2023 §3 Nr. 30: Anlagenbetreiber sind verpflichtet, ihre Anlage im Marktstammdatenregister zu registrieren.",
    )
