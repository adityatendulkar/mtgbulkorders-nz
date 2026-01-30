"""MILP optimisation for card purchases."""

import json
import pulp

# Constants
BIG_M = 9999.0  # Price representing unavailable cards


def validate_tag_constraints(tag_constraints, card_tags, available_mandatory, available_optional):
    """Validate that tag constraints can be satisfied with available cards.
    
    Args:
        tag_constraints: Dictionary mapping tag -> {minimum, maximum, target}
        card_tags: Dictionary mapping card_name (lowercase) -> list of tags
        available_mandatory: List of available mandatory cards
        available_optional: List of available optional cards
        
    Raises:
        ValueError: If constraints cannot be satisfied
    """
    errors = []
    
    for tag, constraints in tag_constraints.items():
        # Count mandatory and optional cards with this tag
        mandatory_with_tag = [c for c in available_mandatory if tag in card_tags.get(c.lower(), [])]
        optional_with_tag = [c for c in available_optional if tag in card_tags.get(c.lower(), [])]
        
        mandatory_count = len(mandatory_with_tag)
        total_available = mandatory_count + len(optional_with_tag)
        
        # Check target constraint
        if 'target' in constraints:
            target = constraints['target']
            if mandatory_count > target:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy target={target}. "
                    f"Already have {mandatory_count} mandatory cards with this tag: {', '.join(mandatory_with_tag)}"
                )
            elif total_available < target:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy target={target}. "
                    f"Only {total_available} cards available with this tag "
                    f"({mandatory_count} mandatory + {len(optional_with_tag)} optional)"
                )
        
        # Check minimum constraint
        if 'minimum' in constraints:
            minimum = constraints['minimum']
            if total_available < minimum:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy minimum={minimum}. "
                    f"Only {total_available} cards available with this tag "
                    f"({mandatory_count} mandatory + {len(optional_with_tag)} optional)"
                )
        
        # Check maximum constraint
        if 'maximum' in constraints:
            maximum = constraints['maximum']
            if mandatory_count > maximum:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy maximum={maximum}. "
                    f"Already have {mandatory_count} mandatory cards with this tag: {', '.join(mandatory_with_tag)}"
                )
        
        # Check if minimum and maximum are compatible
        if 'minimum' in constraints and 'maximum' in constraints:
            if constraints['minimum'] > constraints['maximum']:
                errors.append(
                    f"Tag '{tag}': minimum ({constraints['minimum']}) is greater than maximum ({constraints['maximum']})"
                )
    
    if errors:
        error_msg = "Tag constraint validation failed:\n   - " + "\n   - ".join(errors)
        raise ValueError(error_msg)
    
    print("Tag constraints validated successfully")


def add_tag_constraints(model, tag_constraints, card_tags, available_mandatory, available_optional, z, y, vendors):
    """Add tag constraints to the optimization model.
    
    Args:
        model: PuLP model to add constraints to
        tag_constraints: Dictionary mapping tag -> {minimum, maximum, target}
        card_tags: Dictionary mapping card_name (lowercase) -> list of tags
        available_mandatory: List of available mandatory cards
        available_optional: List of available optional cards
        z: Decision variables for card-vendor purchases
        y: Decision variables for optional card selection
        vendors: Set of vendors
    """
    for tag, constraints in tag_constraints.items():
        # Find mandatory and optional cards with this tag
        mandatory_with_tag = [c for c in available_mandatory if tag in card_tags.get(c.lower(), [])]
        optional_with_tag = [c for c in available_optional if tag in card_tags.get(c.lower(), [])]
        
        # Build expression for total cards with this tag
        # Mandatory cards are always purchased (sum over vendors = 1)
        # Optional cards depend on y[c]
        tag_total = (
            len(mandatory_with_tag) +  # Mandatory cards always count
            pulp.lpSum(y[c] for c in optional_with_tag)  # Optional cards only count if selected
        )
        
        # Add constraints based on what's specified
        if 'target' in constraints:
            # Exact target
            model += tag_total == constraints['target'], f"tag_{tag}_target"
        else:
            # Min/max constraints
            if 'minimum' in constraints:
                model += tag_total >= constraints['minimum'], f"tag_{tag}_min"
            if 'maximum' in constraints:
                model += tag_total <= constraints['maximum'], f"tag_{tag}_max"


def optimise_purchases(K_json_or_file, shipping_costs, vendor_penalty, vendor_discounts=None, mandatory_cards=None, optional_cards=None, min_optional_cards=0, cities_im_in=None, card_tags=None, tag_constraints=None):
    """Solve the MILP to minimize total cost.
    
    Args:
        K_json_or_file: Either a list of price dictionaries or a string file path to load from
        shipping_costs: Dictionary of shipping costs per vendor
        vendor_penalty: Penalty cost for each vendor used
        vendor_discounts: Optional dictionary of discount multipliers per vendor
        mandatory_cards: List of cards that must be purchased
        optional_cards: List of cards that may be purchased
        min_optional_cards: Minimum number of optional cards to purchase
        cities_im_in: List of cities where pickup is available
        card_tags: Dictionary mapping card_name (lowercase) -> list of tags
        tag_constraints: Dictionary mapping tag -> {minimum, maximum, target}
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
    if card_tags is None:
        card_tags = {}
    if tag_constraints is None:
        tag_constraints = {}
    for vendor in shipping_costs:
        if shipping_costs[vendor][1] in cities_im_in:
            shipping_costs[vendor] = shipping_costs[vendor][2]  # Pick up cost
        else:
            shipping_costs[vendor] = shipping_costs[vendor][0]  # Use the first element (shipping cost)

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
    
    # List of all cards to consider in optimisation
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
    
    # Validate tag constraints against available cards
    if tag_constraints:
        print("\n   Validating tag constraints...")
        validate_tag_constraints(tag_constraints, card_tags, available_mandatory, available_optional)
    
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
    
    # Tag constraints
    if tag_constraints:
        add_tag_constraints(model, tag_constraints, card_tags, available_mandatory, available_optional, z, y, vendors)
    
    # Linking constraint: can only buy from vendor if we use that vendor
    for v in vendors:
        for c in cards:
            model += z[v, c] <= x[v]
    
    # Solve
    print("\nSolving optimisation problem...")
    model.solve()
    
    # Check if solution is feasible
    if model.status != pulp.LpStatusOptimal:
        status_name = pulp.LpStatus[model.status]
        if model.status == pulp.LpStatusInfeasible:
            raise ValueError(
                f"No feasible solution found. The constraints cannot be satisfied simultaneously.\n"
                f"   This may be due to conflicting tag constraints or insufficient available cards.\n"
                f"   Status: {status_name}"
            )
        else:
            raise ValueError(
                f"Optimization failed with status: {status_name}\n"
                f"   Please check your configuration and try again."
            )
    
    return model, x, z, y, vendors, cards, K, unavailable_cards, available_mandatory, available_optional


def save_results(model, x, z, y, vendors, cards, K, shipping_costs, unavailable_cards, available_mandatory, available_optional, output_file="results.txt"):
    """Save optimisation results to file."""
    total_cost = 0
    mandatory_purchased = 0
    optional_purchased = 0
    
    with open(output_file, "w") as f:
        f.write(f"Status: {pulp.LpStatus[model.status]}\n\n")
        
        for v in vendors:
            purchased_cards = [c for c in cards if z[v, c].value() == 1]

            if not purchased_cards:
                continue  # Skip vendor entirely if no cards bought

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
