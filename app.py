"""
Flask GUI for the MTG card optimiser.
"""

import copy
import json
from pathlib import Path
from queue import Queue, Empty
import threading
import time

import pulp
import requests
import yaml
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from optimiser import BIG_M, optimise_purchases, save_results
from price_scraper import scrape_prices
from run_optimiser import load_config, parse_card_with_tags


CONFIG_PATH = Path("config.yaml")
RESULTS_PATH = Path("results.txt")

SCRYFALL_CATALOG_URL = "https://api.scryfall.com/catalog/card-names"
SCRYFALL_CACHE_PATH = Path("data/scryfall_card_names.json")
SCRYFALL_CACHE_MAX_AGE_SEC = 7 * 24 * 60 * 60  # 7 days
CARD_NAMES_MAX_SUGGESTIONS = 10

app = Flask(__name__)


def _load_card_names():
    """Load Scryfall card names from cache or fetch once and cache. One API call, cache for 7 days."""
    if SCRYFALL_CACHE_PATH.exists():
        age = time.time() - SCRYFALL_CACHE_PATH.stat().st_mtime
        if age < SCRYFALL_CACHE_MAX_AGE_SEC:
            with SCRYFALL_CACHE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
    SCRYFALL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        SCRYFALL_CATALOG_URL,
        headers={"User-Agent": "CardOptimiser/1.0", "Accept": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    with SCRYFALL_CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


# Unicode dash/minus variants to normalise to ASCII hyphen (incl. en dash U+2013, em dash U+2014)
_UNICODE_DASHES = (
    "\u00AD",  # soft hyphen
    "\u2010",  # hyphen
    "\u2011",  # non-breaking hyphen
    "\u2012",  # figure dash
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u2015",  # horizontal bar
    "\u2212",  # minus sign
    "\u2796",  # heavy minus
    "\u2E3A",  # two-em dash
    "\u2E3B",  # three-em dash
    "\uFE58",  # small em dash
    "\uFE63",  # small hyphen-minus
    "\uFF0D",  # fullwidth hyphen-minus
)


def _normalise_dashes(s):
    """Replace Unicode dash/minus variants (en dash, em dash, etc.) with ASCII hyphen so card names match."""
    if not s:
        return s
    for char in _UNICODE_DASHES:
        s = s.replace(char, "-")
    return s


def _clean_tag(tag):
    return _normalise_dashes(str(tag).strip().lower())


def _clean_name(name):
    return str(name).strip()


def _parse_cards_with_tags(card_entries):
    parsed = []
    for raw_card in card_entries or []:
        card_name, tags = parse_card_with_tags(str(raw_card))
        card_name = _clean_name(card_name)
        if not card_name:
            continue
        clean_tags = []
        for tag in tags:
            cleaned = _clean_tag(tag)
            if cleaned and cleaned not in clean_tags:
                clean_tags.append(cleaned)
        parsed.append({"name": card_name, "tags": clean_tags})
    return parsed


def _extract_initial_data():
    config = load_config(str(CONFIG_PATH))

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    mandatory_cards = _parse_cards_with_tags(raw_config.get("cards", []))
    optional_cards = _parse_cards_with_tags(raw_config.get("optional_cards", []))

    pickup_cities = raw_config.get("pickup_cities", {}) or {}
    cities = sorted(pickup_cities.keys())
    selected_cities = sorted(city for city, enabled in pickup_cities.items() if enabled)

    tag_constraints = []
    raw_constraints = config.get("tag_constraints", {}) or {}
    for tag, constraint in raw_constraints.items():
        if not isinstance(constraint, dict):
            continue
        tag_constraints.append(
            {
                "tag": _clean_tag(tag),
                "minimum": constraint.get("minimum", ""),
                "maximum": constraint.get("maximum", ""),
                "target": constraint.get("target", ""),
            }
        )

    known_tags = set()
    for card in mandatory_cards + optional_cards:
        known_tags.update(card["tags"])
    known_tags.update(_clean_tag(tag) for tag in raw_constraints.keys())

    return {
        "vendor_penalty": float(config.get("vendor_penalty", 0)),
        "min_optional_cards": int(config.get("min_optional_cards", 0)),
        "vendors": list(config.get("vendors", [])),
        "selected_vendors": list(config.get("vendors", [])),
        "cities": cities,
        "selected_cities": selected_cities,
        "mandatory_cards": mandatory_cards,
        "optional_cards": optional_cards,
        "tag_library": sorted(tag for tag in known_tags if tag),
        "tag_constraints": sorted(tag_constraints, key=lambda item: item["tag"]),
        "price_data_file": config.get("price_data_file") or "",
    }


def _normalise_cards(cards_payload):
    cards = []
    for item in cards_payload or []:
        if not isinstance(item, dict):
            continue
        name = _clean_name(item.get("name", ""))
        if not name:
            continue
        raw_tags = item.get("tags", []) or []
        clean_tags = []
        for tag in raw_tags:
            cleaned = _clean_tag(tag)
            if cleaned and cleaned not in clean_tags:
                clean_tags.append(cleaned)
        cards.append({"name": name, "tags": clean_tags})
    return cards


def _normalise_constraints(constraint_rows):
    constraints = {}
    for row in constraint_rows or []:
        if not isinstance(row, dict):
            continue
        tag = _clean_tag(row.get("tag", ""))
        if not tag:
            continue
        parsed = {}
        for key in ("minimum", "maximum", "target"):
            value = row.get(key, "")
            if value in ("", None):
                continue
            parsed[key] = int(value)
        if parsed:
            constraints[tag] = parsed
    return constraints


def _build_card_tag_map(mandatory_cards, optional_cards):
    card_tags = {}
    for card in mandatory_cards + optional_cards:
        if card["tags"]:
            card_tags[_clean_tag(card["name"])] = card["tags"]
    return card_tags


def _build_complete_price_data(price_rows, vendors, cards):
    vendor_set = {_clean_tag(vendor) for vendor in vendors}
    card_set = {_clean_tag(card) for card in cards}

    cheapest = {}
    for row in price_rows or []:
        if not isinstance(row, dict):
            continue
        vendor = _clean_tag(row.get("vendor", ""))
        card = _clean_tag(row.get("card", ""))
        if vendor not in vendor_set or card not in card_set:
            continue
        try:
            price = float(row.get("price", BIG_M))
        except (TypeError, ValueError):
            price = BIG_M
        key = (vendor, card)
        cheapest[key] = min(price, cheapest.get(key, BIG_M))

    complete = []
    for card in sorted(card_set):
        for vendor in sorted(vendor_set):
            complete.append(
                {
                    "vendor": vendor,
                    "card": card,
                    "price": cheapest.get((vendor, card), BIG_M),
                }
            )
    return complete


def _format_card_quantity_list(card_quantities):
    labels = []
    for card, quantity in sorted((card_quantities or {}).items()):
        if int(quantity) <= 1:
            labels.append(card)
        else:
            labels.append(f"{card} x{int(quantity)}")
    return labels


def _build_summary(
    model,
    x,
    z,
    y,
    vendors,
    cards,
    K,
    shipping_costs,
    mandatory_card_quantities,
    optional_card_quantities,
    unavailable_cards,
):
    vendor_summaries = []
    total_cost = 0.0
    total_card_cost = 0.0
    total_shipping_cost = 0.0

    optional_card_set = set(optional_card_quantities)

    for vendor in sorted(vendors):
        if x[vendor].value() != 1:
            continue
        purchased_cards = []
        shipping = float(shipping_costs.get(vendor, 0))
        subtotal = shipping
        total_shipping_cost += shipping
        for card in sorted(cards):
            quantity = int(round(z[vendor, card].value() or 0))
            if quantity <= 0:
                continue
            price = float(K.get((vendor, card), BIG_M))
            line_total = price * quantity
            subtotal += line_total
            total_card_cost += line_total
            purchased_cards.append(
                {
                    "name": card,
                    "quantity": quantity,
                    "price": round(price, 2),
                    "line_total": round(line_total, 2),
                    "optional": card in optional_card_set,
                }
            )
        total_cost += subtotal
        vendor_summaries.append(
            {
                "vendor": vendor,
                "shipping": round(shipping, 2),
                "subtotal": round(subtotal, 2),
                "cards": purchased_cards,
            }
        )

    optional_not_purchased_map = {}
    for card, requested_quantity in optional_card_quantities.items():
        purchased_quantity = int(round(y[card].value() or 0))
        missing_quantity = requested_quantity - purchased_quantity
        if missing_quantity > 0:
            optional_not_purchased_map[card] = missing_quantity

    optional_not_purchased = _format_card_quantity_list(optional_not_purchased_map)
    mandatory_count = sum(
        card["quantity"]
        for vendor_data in vendor_summaries
        for card in vendor_data["cards"]
        if not card["optional"]
    )
    optional_count = sum(
        card["quantity"]
        for vendor_data in vendor_summaries
        for card in vendor_data["cards"]
        if card["optional"]
    )

    return {
        "status": pulp.LpStatus[model.status],
        "total_cost": round(total_cost, 2),
        "card_cost": round(total_card_cost, 2),
        "shipping_cost": round(total_shipping_cost, 2),
        "mandatory_count": mandatory_count,
        "optional_count": optional_count,
        "vendor_summaries": vendor_summaries,
        "optional_not_purchased": optional_not_purchased,
        "unavailable_cards": _format_card_quantity_list(unavailable_cards),
    }


def _stream_scrape_events(mandatory_names, optional_names, selected_vendors):
    """Generator that runs scrape_prices in a thread and yields SSE events."""
    queue = Queue()
    result_holder = []

    def progress_callback(current, total, card_name):
        queue.put({"type": "progress", "current": current, "total": total, "card": card_name})

    def run_scrape():
        try:
            data = scrape_prices(
                mandatory_names,
                selected_vendors,
                optional_names,
                progress_callback=progress_callback,
            )
            result_holder.append(data)
            queue.put({"type": "complete", "price_data": data})
        except Exception as e:
            queue.put({"type": "error", "error": str(e)})

    thread = threading.Thread(target=run_scrape)
    thread.start()

    while True:
        try:
            event = queue.get(timeout=300)
        except Empty:
            yield f"event: error\ndata: {json.dumps({'error': 'Scrape timeout'})}\n\n"
            break
        if event["type"] == "progress":
            yield f"event: progress\ndata: {json.dumps(event)}\n\n"
        elif event["type"] == "complete":
            yield f"event: complete\ndata: {json.dumps({'price_data': event['price_data']})}\n\n"
            break
        elif event["type"] == "error":
            yield f"event: error\ndata: {json.dumps({'error': event['error']})}\n\n"
            break


@app.route("/scrape", methods=["POST"])
def scrape():
    """Stream scraping progress via Server-Sent Events, then return price data in final event."""
    payload = request.get_json(silent=True) or {}
    try:
        base_config = load_config(str(CONFIG_PATH))
    except Exception as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    all_vendors = set(base_config.get("vendors", []))
    selected_vendors = []
    for vendor in payload.get("vendors", []):
        vendor_clean = _clean_tag(vendor)
        if vendor_clean in all_vendors and vendor_clean not in selected_vendors:
            selected_vendors.append(vendor_clean)
    if not selected_vendors:
        return jsonify({"ok": False, "error": "Select at least one store."}), 400

    mandatory_cards = _normalise_cards(payload.get("mandatory_cards", []))
    optional_cards = _normalise_cards(payload.get("optional_cards", []))
    if not mandatory_cards and not optional_cards:
        return jsonify({"ok": False, "error": "Add at least one mandatory or optional card."}), 400

    mandatory_names = [c["name"] for c in mandatory_cards]
    optional_names = [c["name"] for c in optional_cards]

    def generate():
        for chunk in _stream_scrape_events(mandatory_names, optional_names, selected_vendors):
            yield chunk

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/card-names")
def api_card_names():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify([])
    try:
        names = _load_card_names()
    except Exception:
        return jsonify([])
    matches = [n for n in names if q in n.lower()][:CARD_NAMES_MAX_SUGGESTIONS]
    return jsonify(matches)


@app.route("/api/card-names/validate")
def api_validate_card_name():
    """Return whether the given name matches a known Scryfall card (case-insensitive)."""
    raw = (request.args.get("name") or "").strip()
    if not raw:
        return jsonify({"valid": False})
    try:
        names = _load_card_names()
    except Exception:
        return jsonify({"valid": False})
    key = raw.lower()
    canonical = next((n for n in names if n.strip().lower() == key), None)
    if canonical is None:
        return jsonify({"valid": False})
    return jsonify({"valid": True, "name": canonical})


@app.route("/")
def index():
    initial_data = _extract_initial_data()
    return render_template("index.html", initial_data=initial_data)


@app.route("/optimise", methods=["POST"])
def optimise():
    payload = request.get_json(silent=True) or {}

    try:
        base_config = load_config(str(CONFIG_PATH))
    except Exception as error:  # pragma: no cover - operational guard
        return jsonify({"ok": False, "error": str(error)}), 400

    all_vendors = set(base_config.get("vendors", []))
    selected_vendors = []
    for vendor in payload.get("vendors", []):
        vendor_clean = _clean_tag(vendor)
        if vendor_clean in all_vendors and vendor_clean not in selected_vendors:
            selected_vendors.append(vendor_clean)

    if not selected_vendors:
        return jsonify({"ok": False, "error": "Select at least one store."}), 400

    mandatory_cards = _normalise_cards(payload.get("mandatory_cards", []))
    optional_cards = _normalise_cards(payload.get("optional_cards", []))

    if not mandatory_cards and not optional_cards:
        return jsonify({"ok": False, "error": "Add at least one mandatory or optional card."}), 400

    card_tags = _build_card_tag_map(mandatory_cards, optional_cards)
    tag_constraints = _normalise_constraints(payload.get("tag_constraints", []))

    known_cities = set((base_config.get("pickup_cities", {}) or {}).keys())
    selected_cities = sorted(
        city for city in payload.get("pickup_cities", []) if city in known_cities
    )

    try:
        vendor_penalty = float(payload.get("vendor_penalty", base_config.get("vendor_penalty", 0)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Vendor penalty must be a valid number."}), 400

    try:
        min_optional_cards = int(payload.get("min_optional_cards", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Minimum optional cards must be an integer."}), 400
    min_optional_cards = max(min_optional_cards, 0)

    mandatory_names = [card["name"] for card in mandatory_cards]
    optional_names = [card["name"] for card in optional_cards]
    all_card_names = mandatory_names + optional_names
    # Normalise names (en/em dash etc. → hyphen) so they match price matrix keys and optimiser
    mandatory_names_canonical = [_clean_tag(n) for n in mandatory_names]
    optional_names_canonical = [_clean_tag(n) for n in optional_names]

    use_saved_prices = bool(payload.get("use_saved_prices", False))
    price_data_file = (base_config.get("price_data_file") or "").strip()
    scraped_price_data = payload.get("scraped_price_data")

    if scraped_price_data is not None:
        price_data = scraped_price_data
    elif use_saved_prices and price_data_file:
        if not Path(price_data_file).exists():
            return jsonify(
                {"ok": False, "error": f"Configured price data file not found: {price_data_file}"}
            ), 400
        with Path(price_data_file).open("r", encoding="utf-8") as handle:
            price_data = json.load(handle)
    else:
        price_data = scrape_prices(mandatory_names, selected_vendors, optional_names)

    complete_price_data = _build_complete_price_data(price_data, selected_vendors, all_card_names)

    shipping_costs = {}
    base_shipping_costs = base_config.get("shipping_costs", {})
    for vendor in selected_vendors:
        if vendor in base_shipping_costs:
            shipping_costs[vendor] = copy.deepcopy(base_shipping_costs[vendor])
        else:
            shipping_costs[vendor] = [0.0, "online", 0.0]

    vendor_discounts = {
        vendor: discount
        for vendor, discount in (base_config.get("vendor_discounts", {}) or {}).items()
        if vendor in selected_vendors
    }

    try:
        (
            model,
            x,
            z,
            y,
            vendors,
            cards,
            K,
            unavailable_cards,
            mandatory_card_quantities,
            optional_card_quantities,
        ) = optimise_purchases(
            complete_price_data,
            shipping_costs,
            vendor_penalty,
            vendor_discounts,
            mandatory_names_canonical,
            optional_names_canonical,
            min_optional_cards,
            selected_cities,
            card_tags,
            tag_constraints,
        )
    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    save_results(
        model,
        x,
        z,
        y,
        vendors,
        cards,
        K,
        shipping_costs,
        unavailable_cards,
        mandatory_card_quantities,
        optional_card_quantities,
        output_file=str(RESULTS_PATH),
    )

    summary = _build_summary(
        model,
        x,
        z,
        y,
        vendors,
        cards,
        K,
        shipping_costs,
        mandatory_card_quantities,
        optional_card_quantities,
        unavailable_cards,
    )
    summary["results_file"] = str(RESULTS_PATH)

    return jsonify({"ok": True, "summary": summary})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
