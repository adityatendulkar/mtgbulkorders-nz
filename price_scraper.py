"""Price scraping functionality for MTG Singles."""

import requests
import time
import json

# Constants
BIG_M = 9999.0  # Price representing unavailable cards


def scrape_prices(cards, vendors, optional_cards=None):
    """Scrape prices from MTG Singles API."""
    if optional_cards is None:
        optional_cards = []
    
    url = "https://api.mtgsingles.co.nz/MtgSingle"
    
    all_cards = list(cards) + list(optional_cards)
    K = {}
    print(f"Scraping prices for {len(all_cards)} cards ({len(cards)} mandatory, {len(optional_cards)} optional)...")
    
    for idx, card in enumerate(all_cards, 1):
        print(f"  [{idx}/{len(all_cards)}] Scraping: {card}", end="")
        
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
            "Accept-Encoding": "gzip, deflate, br",
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
                        time.sleep(0.5)
                        continue
                    print(f" - Failed (status {r.status_code})")
                    break
                
                if not r.text.strip():
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
                        continue
                    print(f" - Empty response")
                    break
                
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
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
                    card_name = card.lower()
                    
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
                    time.sleep(3 + attempt * 2)  # Increasing delay
                else:
                    print(f" - All attempts failed")
            finally:
                session.close()
        
        # Longer delay between cards to be more gentle
        if idx < len(all_cards):
            time.sleep(1 + (idx % 3))  # 1-3 second delay
    
    # Build structured data for MILP
    cards_set = sorted({card for (card, _) in K.keys()})
    
    K_temp = []
    for card in cards_set:
        for vendor in vendors:
            price = K.get((card, vendor), BIG_M)
            K_temp.append({
                "card": card,
                "vendor": vendor,
                "price": price
            })
    
    return K_temp
