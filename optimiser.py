"""MILP optimisation for card purchases."""

import json
import pulp

# Constants
BIG_M = 9999.0  # Price representing unavailable cards


def optimise_purchases(K_json_or_file, shipping_costs, vendor_penalty, vendor_discounts=None, mandatory_cards=None, optional_cards=None, min_optional_cards=0):
    """Solve the MILP to minimize total cost.
    
    Args:
        K_json_or_file: Either a list of price dictionaries or a string file path to load from
        shipping_costs: Dictionary of shipping costs per vendor
        vendor_penalty: Penalty cost for each vendor used
        vendor_discounts: Optional dictionary of discount multipliers per vendor
        mandatory_cards: List of cards that must be purchased
        optional_cards: List of cards that may be purchased
        min_optional_cards: Minimum number of optional cards to purchase
    """
    # Handle both file path and variable input
    if isinstance(K_json_or_file, str):
        # It's a file path, load it
        with open(K_json_or_file, "r") as f:
            K_json = json.load(f)
    else:
        # It's already the data
        K_json = K_json_or_file
    
    if vendor_discounts is None:
        vendor_discounts = {}
    if mandatory_cards is None:
        mandatory_cards = []
    if optional_cards is None:
        optional_cards = []
    
    # Convert to lowercase for matching
    mandatory_cards_lower = set(c.lower() for c in mandatory_cards)
    optional_cards_lower = set(c.lower() for c in optional_cards)
    
    vendors = set(item["vendor"] for item in K_json)
    all_cards = set(item["card"] for item in K_json)
    
    K = {
        (item["vendor"], item["card"]): item["price"] for item in K_json
    }
    
    # Apply vendor-specific discounts from config
    for key in list(K.keys()):
        vendor = key[0]
        if vendor in vendor_discounts:
            K[key] *= vendor_discounts[vendor]
    
    # Identify unavailable cards (all prices are BIG_M)
    unavailable_mandatory = []
    unavailable_optional = []
    available_mandatory = []
    available_optional = []
    
    for card in all_cards:
        min_price = min(K.get((v, card), BIG_M) for v in vendors)
        is_mandatory = card in mandatory_cards_lower
        is_optional = card in optional_cards_lower
        
        if min_price >= BIG_M:
            if is_mandatory:
                unavailable_mandatory.append(card)
            elif is_optional:
                unavailable_optional.append(card)
        else:
            if is_mandatory:
                available_mandatory.append(card)
            elif is_optional:
                available_optional.append(card)
    
    cards = set(available_mandatory + available_optional)
    unavailable_cards = unavailable_mandatory + unavailable_optional
    
    if unavailable_mandatory:
        print(f"\n   WARNING: {len(unavailable_mandatory)} MANDATORY card(s) not available:")
        for card in sorted(unavailable_mandatory):
            print(f"     - {card}")
    
    if unavailable_optional:
        print(f"\n   Note: {len(unavailable_optional)} optional card(s) not available:")
        for card in sorted(unavailable_optional):
            print(f"     - {card}")
    
    if unavailable_mandatory or unavailable_optional:
        print(f"\n   Optimising for {len(available_mandatory)} mandatory + {len(available_optional)} optional cards...\n")
    
    # Create problem
    model = pulp.LpProblem("MTG_Min_Cost", pulp.LpMinimize)
    
    # Decision variables
    z = pulp.LpVariable.dicts(
        "z", [(v, c) for v in vendors for c in cards],
        cat="Binary"
    )
    
    x = pulp.LpVariable.dicts(
        "x", vendors,
        cat="Binary"
    )
    
    # Decision variable for whether an optional card is purchased
    y = pulp.LpVariable.dicts(
        "y", available_optional,
        cat="Binary"
    )
    
    # Objective function
    model += (
        pulp.lpSum(K[v, c] * z[v, c] for v in vendors for c in cards)
        + pulp.lpSum(shipping_costs.get(v, 0) * x[v] for v in vendors)
        + vendor_penalty * pulp.lpSum(x[v] for v in vendors)
    )
    
    # Constraints: Each mandatory card bought exactly once
    for c in available_mandatory:
        model += pulp.lpSum(z[v, c] for v in vendors) == 1
    
    # Constraints: Each optional card bought at most once (only if y[c] = 1)
    for c in available_optional:
        model += pulp.lpSum(z[v, c] for v in vendors) == y[c]
    
    # Constraint: Minimum number of optional cards must be purchased
    if available_optional and min_optional_cards > 0:
        actual_min = min(min_optional_cards, len(available_optional))
        model += pulp.lpSum(y[c] for c in available_optional) >= actual_min
    
    # Linking constraint: can only buy from vendor if we use that vendor
    for v in vendors:
        for c in cards:
            model += z[v, c] <= x[v]
    
    # Solve
    print("\nSolving optimisation problem...")
    model.solve()
    
    return model, x, z, y, vendors, cards, K, unavailable_cards, available_mandatory, available_optional


def save_results(model, x, z, y, vendors, cards, K, shipping_costs, unavailable_cards, available_mandatory, available_optional, output_file="results.txt"):
    """Save optimisation results to file."""
    total_cost = 0
    mandatory_purchased = 0
    optional_purchased = 0
    
    with open(output_file, "w") as f:
        f.write(f"Status: {pulp.LpStatus[model.status]}\n\n")
        
        for v in vendors:
            if x[v].value() == 1:
                vendor_total = shipping_costs.get(v, 0)  # Start with shipping cost
                f.write(f"Use vendor: {v} (shipping: ${shipping_costs.get(v, 0):.2f})\n")
                
                for c in cards:
                    if z[v, c].value() == 1:
                        price = K[(v.lower(), c.lower())]
                        vendor_total += price
                        is_optional = c in available_optional
                        card_type = " [OPTIONAL]" if is_optional else ""
                        f.write(f"  Buy {c} at ${price:.2f}{card_type}\n")
                        
                        if is_optional:
                            optional_purchased += 1
                        else:
                            mandatory_purchased += 1
                
                total_cost += vendor_total
                f.write(f"  Subtotal for {v}: ${vendor_total:.2f}\n\n")
        
        f.write(f"Total cost (including shipping): ${total_cost:.2f}\n")
        f.write(f"Cards purchased: {mandatory_purchased} mandatory, {optional_purchased} optional\n")
        
        # Determine which optional cards were not purchased
        optional_not_purchased = [c for c in available_optional if y[c].value() == 0]
        
        if optional_not_purchased:
            f.write(f"\n" + "=" * 60 + "\n")
            f.write(f"OPTIONAL CARDS NOT PURCHASED ({len(optional_not_purchased)}):")
            f.write(f"\nThe following optional cards were available but not selected by the optimiser:\n\n")
            for card in sorted(optional_not_purchased):
                f.write(f"  - {card}\n")
        
        if unavailable_cards:
            f.write(f"\n" + "=" * 60 + "\n")
            f.write(f"UNAVAILABLE CARDS ({len(unavailable_cards)}):")
            f.write(f"\nThe following cards were not available from any vendor:\n\n")
            for card in sorted(unavailable_cards):
                f.write(f"  - {card}\n")
    
    print(f"\nResults saved to {output_file}")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Cards purchased: {mandatory_purchased} mandatory, {optional_purchased}/{len(available_optional)} optional")
    if optional_not_purchased:
        print(f"Optional cards not purchased: {len(optional_not_purchased)}")
    if unavailable_cards:
        print(f"Unavailable cards: {len(unavailable_cards)}")
