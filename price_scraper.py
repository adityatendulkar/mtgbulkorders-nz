"""Price scraping functionality for MTG Singles."""

import requests
import time
import json

# Constants
BIG_M = 9999.0  # Price representing unavailable cards


# Unicode dash/minus variants to normalise to ASCII hyphen (en dash U+2013, em dash U+2014, etc.)
_UNICODE_DASHES = (
    "\u00AD", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015",
    "\u2212", "\u2796", "\u2E3A", "\u2E3B", "\uFE58", "\uFE63", "\uFF0D",
)


def _normalise_card_name(name):
    """Canonical form for matching: strip, lower, and normalise Unicode dashes (en/em dash, etc.) to ASCII hyphen."""
    if not name:
        return name
    s = str(name).strip().lower()
    for char in _UNICODE_DASHES:
        s = s.replace(char, "-")
    return s


def scrape_prices(cards, vendors, optional_cards=None, progress_callback=None):
    """Scrape prices from MTG Singles API. progress_callback(current, total, card_name) is called per card."""
    if optional_cards is None:
        optional_cards = []
    
    url = "https://api.mtgsingles.co.nz/MtgSingle"
    
    all_cards = list(cards) + list(optional_cards)
    # Deduplicate by name (case-insensitive, dash-normalised) so we only scrape each name once
    seen = set()
    unique_cards_ordered = []
    for c in all_cards:
        key = _normalise_card_name(c)
        if key and key not in seen:
            seen.add(key)
            unique_cards_ordered.append(key)
    total_unique = len(unique_cards_ordered)
    total = len(all_cards)
    if total_unique < total:
        print(f"Scraping prices for {total_unique} unique cards (from {total} entries)...")
    else:
        print(f"Scraping prices for {total} cards ({len(cards)} mandatory, {len(optional_cards)} optional)...")
    
    K = {}
    for idx, card in enumerate(unique_cards_ordered, 1):
        if progress_callback:
            progress_callback(idx, total_unique, card)
        print(f"  [{idx}/{total_unique}] Scraping: {card}", end="")
        
        # Create fresh session for each request to avoid connection issues
        session = requests.Session()
        
        # Rotate user agents to appear more like different browsers
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        ]
        
        HEADERS = {
            "User-Agent": user_agents[idx % len(user_agents)],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-NZ,en-US;q=0.9,en;q=0.8",
            # Avoid brotli here; environments without brotli support will fail JSON parsing.
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://mtgsingles.co.nz/",
            "Origin": "https://mtgsingles.co.nz",
            "DNT": "1",
            "Connection": "close",  # Close connection after each request
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
        
        params = {
            "query": card,
            "page": 1,
            "pageSize": 20,
            "Country": 1
        }
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                r = session.get(url, headers=HEADERS, params=params, timeout=15)
                
                if r.status_code != 200:
                    if attempt < max_attempts - 1:
                        time.sleep(0.2)
                        continue
                    print(f" - Failed (status {r.status_code})")
                    break
                
                if not r.text.strip():
                    if attempt < max_attempts - 1:
                        time.sleep(0.2)
                        continue
                    print(f" - Empty response")
                    break

                content_type = r.headers.get("Content-Type", "").lower()
                if "application/json" not in content_type:
                    if attempt < max_attempts - 1:
                        time.sleep(0.2)
                        continue
                    print(f" - Unexpected content type: {content_type or 'unknown'}")
                    break
                
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    if attempt < max_attempts - 1:
                        time.sleep(0.2)
                        continue
                    print(f" - Invalid JSON")
                    break
                
                if not data:
                    print(f" - No results")
                    break
                
                found_count = 0
                for listing in data:
                    if card.lower() not in listing["title"].lower():
                        continue
                    
                    price = float(listing["price"].replace("$", "").replace(",", ""))
                    vendor = listing["store"].replace("NZ/", "").lower()
                    card_name = _normalise_card_name(card)
                    
                    key = (card_name, vendor)
                    
                    # Keep cheapest price only
                    if key not in K or price < K[key]:
                        K[key] = price
                        found_count += 1
                
                print(f" - Found {found_count} prices")
                break
            
            except requests.exceptions.RequestException as e:
                if attempt < max_attempts - 1:
                    print(f" - Attempt {attempt + 1} failed, retrying...")
                    time.sleep(0.5 + attempt * 0.5)  # Smaller increasing backoff
                else:
                    print(f" - All attempts failed")
            finally:
                session.close()
        
        # Delay between cards
        if idx < total_unique:
            time.sleep(0.2)
    
    # Build structured data for MILP (canonical card names so they match app.py _clean_tag)
    all_cards_canonical = [_normalise_card_name(c) for c in all_cards]
    
    K_temp = []
    for card in sorted(all_cards_canonical):
        for vendor in vendors:
            price = K.get((card, vendor), BIG_M)
            K_temp.append({
                "card": card,
                "vendor": vendor,
                "price": price
            })
    
    return K_temp
