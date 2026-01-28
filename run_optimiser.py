"""
MTG Card Optimiser - Main Entry Point
Scrapes prices, optimises vendor selection, and outputs purchasing plan
"""

import json
import os
import yaml
from datetime import datetime

from price_scraper import scrape_prices
from optimiser import optimise_purchases, save_results


def load_config(config_file="config.yaml"):
    """Load configuration from YAML config file."""
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file '{config_file}' not found. Please create it first.")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML config file: {e}")
    
    # Validate required fields
    required_fields = ["vendor_penalty", "vendors", "shipping_costs", "cards"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field '{field}' in config file")
    
    # Validate vendor_penalty is a number
    if not isinstance(config["vendor_penalty"], (int, float)):
        raise ValueError("vendor_penalty must be a number")
    
    # Validate vendors is a list
    if not isinstance(config["vendors"], list):
        raise ValueError("vendors must be a list")
    
    # Validate shipping_costs is a dict
    if not isinstance(config["shipping_costs"], dict):
        raise ValueError("shipping_costs must be a dictionary")
    
    # Validate cards is a list
    if not isinstance(config["cards"], list):
        raise ValueError("cards must be a list")
    
    # Add vendor discounts if present, default to empty dict
    if "vendor_discounts" not in config:
        config["vendor_discounts"] = {}
    
    # Add optional_cards if present, default to empty list
    if "optional_cards" not in config:
        config["optional_cards"] = []
    
    # Add min_optional_cards if present, default to 0
    if "min_optional_cards" not in config:
        config["min_optional_cards"] = 0
    
    # Validate optional_cards is a list
    if not isinstance(config["optional_cards"], list):
        raise ValueError("optional_cards must be a list")
    
    # Validate min_optional_cards is a number
    if not isinstance(config["min_optional_cards"], (int, float)):
        raise ValueError("min_optional_cards must be a number")
    
    # Add price_data_file if present, default to None
    if "price_data_file" not in config:
        config["price_data_file"] = None
    
    return config


def main():
    """Main execution function."""
    print("=" * 60)
    print("MTG Card Purchase Optimiser")
    print("=" * 60)
    
    # Load configuration
    print("\n1. Loading configuration...")
    try:
        config = load_config("config.yaml")
    except (FileNotFoundError, ValueError) as e:
        print(f"\nError: {e}")
        return
    
    print(f"   - Vendor penalty: ${config['vendor_penalty']:.2f}")
    print(f"   - Vendors: {len(config['vendors'])}")
    print(f"   - Mandatory cards: {len(config['cards'])}")
    print(f"   - Optional cards: {len(config['optional_cards'])}")
    if config['min_optional_cards'] > 0:
        print(f"   - Minimum optional cards required: {config['min_optional_cards']}")
    if config.get('vendor_discounts'):
        print(f"   - Vendor discounts: {len(config['vendor_discounts'])} configured")
    
    # Ensure prices directory exists
    os.makedirs("prices", exist_ok=True)
    
    # Use price data from config file or scrape fresh data
    if config.get('price_data_file'):
        print(f"\n2. Loading price data from config file: {config['price_data_file']}")
        with open(config['price_data_file'], "r") as f:
            price_data = json.load(f)
        print(f"   Loaded data for {len(set(item['card'] for item in price_data))} cards")
    else:
        # Scrape prices
        print("\n2. Scraping fresh price data...")
        print("   This may take several minutes...")
        price_data = scrape_prices(config["cards"], config["vendors"], config["optional_cards"])
        
        # Save scraped data with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prices_file = f"prices/prices_{timestamp}.json"
        with open(prices_file, "w") as f:
            json.dump(price_data, f, indent=2)
        print(f"\n   Scraped data saved to {prices_file} and stored in variable")
    
    # Optimise
    print("\n3. Optimising purchase plan...")
    # Pass the variable directly to optimisation (can also pass file path)
    model, x, z, y, vendors, cards, K, unavailable_cards, available_mandatory, available_optional = optimise_purchases(
        price_data,  # Pass variable instead of file path
        config["shipping_costs"], 
        config["vendor_penalty"],
        config.get("vendor_discounts", {}),
        config["cards"],
        config["optional_cards"],
        config["min_optional_cards"]
    )
    
    # Save results
    print("\n4. Saving results...")
    save_results(model, x, z, y, vendors, cards, K, config["shipping_costs"], unavailable_cards, available_mandatory, available_optional)
    
    print("\n" + "=" * 60)
    print("Optimisation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
