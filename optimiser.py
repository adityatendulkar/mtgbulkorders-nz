"""MILP optimisation for card purchases."""

import json
import os
import platform
import shutil
from collections import Counter
import pulp

# Constants
BIG_M = 9999.0  # Price representing unavailable cards


def _build_solver_candidates():
    """Build ordered solver candidates for cross-platform compatibility."""
    candidates = []
    seen = set()

    def add_coin_solver(name, path):
        if not path:
            return
        abs_path = os.path.abspath(path)
        if not (os.path.isfile(abs_path) and os.access(abs_path, os.X_OK)):
            return
        key = ("coin_cmd", abs_path)
        if key in seen:
            return
        seen.add(key)
        candidates.append((name, pulp.COIN_CMD(path=abs_path, msg=False)))

    # Prefer explicitly installed CBC first.
    add_coin_solver("cbc_on_path", shutil.which("cbc"))

    # Common macOS locations (useful when PATH differs between shells/apps).
    if platform.system().lower() == "darwin":
        add_coin_solver("cbc_homebrew_opt", "/opt/homebrew/bin/cbc")
        add_coin_solver("cbc_homebrew_usr_local", "/usr/local/bin/cbc")

    # Fallback to PuLP bundled CBC (typically works on Windows and Intel macOS).
    candidates.append(("pulp_bundled_cbc", pulp.PULP_CBC_CMD(msg=False)))
    return candidates


def _format_card_count_list(card_counts):
    """Return card labels like 'name x3' for diagnostics."""
    labels = []
    for card, count in sorted(card_counts.items()):
        if count <= 1:
            labels.append(card)
        else:
            labels.append(f"{card} x{count}")
    return labels


def validate_tag_constraints(tag_constraints, card_tags, mandatory_qty, optional_qty):
    """Validate that tag constraints can be satisfied with available cards.
    
    Args:
        tag_constraints: Dictionary mapping tag -> {minimum, maximum, target}
        card_tags: Dictionary mapping card_name (lowercase) -> list of tags
        mandatory_qty: Dict mapping mandatory card_name -> required quantity
        optional_qty: Dict mapping optional card_name -> max selectable quantity
        
    Raises:
        ValueError: If constraints cannot be satisfied
    """
    errors = []
    
    for tag, constraints in tag_constraints.items():
        mandatory_with_tag = {
            card: qty
            for card, qty in mandatory_qty.items()
            if tag in card_tags.get(card.lower(), [])
        }
        optional_with_tag = {
            card: qty
            for card, qty in optional_qty.items()
            if tag in card_tags.get(card.lower(), [])
        }

        mandatory_count = sum(mandatory_with_tag.values())
        optional_count = sum(optional_with_tag.values())
        total_available = mandatory_count + optional_count
        
        # Check target constraint
        if 'target' in constraints:
            target = constraints['target']
            if mandatory_count > target:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy target={target}. "
                    f"Already have {mandatory_count} mandatory cards with this tag: "
                    f"{', '.join(_format_card_count_list(mandatory_with_tag)) or 'none'}"
                )
            elif total_available < target:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy target={target}. "
                    f"Only {total_available} cards available with this tag "
                    f"({mandatory_count} mandatory + {optional_count} optional)"
                )
        
        # Check minimum constraint
        if 'minimum' in constraints:
            minimum = constraints['minimum']
            if total_available < minimum:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy minimum={minimum}. "
                    f"Only {total_available} cards available with this tag "
                    f"({mandatory_count} mandatory + {optional_count} optional)"
                )
        
        # Check maximum constraint
        if 'maximum' in constraints:
            maximum = constraints['maximum']
            if mandatory_count > maximum:
                errors.append(
                    f"Tag '{tag}': Cannot satisfy maximum={maximum}. "
                    f"Already have {mandatory_count} mandatory cards with this tag: "
                    f"{', '.join(_format_card_count_list(mandatory_with_tag)) or 'none'}"
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


def add_tag_constraints(model, tag_constraints, card_tags, mandatory_qty, optional_qty, y):
    """Add tag constraints to the optimization model.
    
    Args:
        model: PuLP model to add constraints to
        tag_constraints: Dictionary mapping tag -> {minimum, maximum, target}
        card_tags: Dictionary mapping card_name (lowercase) -> list of tags
        mandatory_qty: Dict mapping mandatory card_name -> required quantity
        optional_qty: Dict mapping optional card_name -> max selectable quantity
        y: Decision variables for optional card selection quantities
    """
    for tag, constraints in tag_constraints.items():
        mandatory_count = sum(
            qty for card, qty in mandatory_qty.items()
            if tag in card_tags.get(card.lower(), [])
        )
        optional_with_tag = [
            card for card in optional_qty
            if tag in card_tags.get(card.lower(), [])
        ]
        
        # Build expression for total cards with this tag
        # Mandatory quantities are fixed; optional quantities depend on y[c]
        tag_total = (
            mandatory_count +
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
    if cities_im_in is None:
        cities_im_in = []
    if card_tags is None:
        card_tags = {}
    if tag_constraints is None:
        tag_constraints = {}
    for vendor in shipping_costs:
        if shipping_costs[vendor][1] in cities_im_in:
            shipping_costs[vendor] = shipping_costs[vendor][2]  # Pick up cost
        else:
            shipping_costs[vendor] = shipping_costs[vendor][0]  # Use the first element (shipping cost)

    # Convert to lowercase and preserve quantity demands
    mandatory_requested = Counter(c.lower() for c in mandatory_cards if c)
    optional_requested = Counter(c.lower() for c in optional_cards if c)
    overlap = sorted(set(mandatory_requested) & set(optional_requested))
    if overlap:
        raise ValueError(
            "Cards cannot be in both mandatory and optional lists at the same time.\n"
            f"   Overlapping card(s): {', '.join(overlap)}"
        )
    
    vendors = set(item["vendor"] for item in K_json)
    demand_cards = set(mandatory_requested) | set(optional_requested)
    
    K = {
        (item["vendor"], item["card"]): item["price"] for item in K_json
    }
    
    # Apply vendor-specific discounts from config
    for key in list(K.keys()):
        vendor = key[0]
        if vendor in vendor_discounts:
            K[key] *= vendor_discounts[vendor]
    
    # Identify unavailable cards (all prices are BIG_M)
    unavailable_mandatory = {}
    unavailable_optional = {}
    available_mandatory_qty = {}
    available_optional_qty = {}

    for card in sorted(demand_cards):
        min_price = min(K.get((v, card), BIG_M) for v in vendors)
        mandatory_qty = mandatory_requested.get(card, 0)
        optional_qty = optional_requested.get(card, 0)

        if min_price >= BIG_M:
            if mandatory_qty > 0:
                unavailable_mandatory[card] = mandatory_qty
            if optional_qty > 0:
                unavailable_optional[card] = optional_qty
        else:
            if mandatory_qty > 0:
                available_mandatory_qty[card] = mandatory_qty
            if optional_qty > 0:
                available_optional_qty[card] = optional_qty

    cards = set(available_mandatory_qty) | set(available_optional_qty)
    unavailable_cards = {**unavailable_mandatory, **unavailable_optional}
    
    if unavailable_mandatory:
        unavailable_qty = sum(unavailable_mandatory.values())
        print(f"\n   WARNING: {unavailable_qty} MANDATORY card copy/copies not available:")
        for card in _format_card_count_list(unavailable_mandatory):
            print(f"     - {card}")
    
    if unavailable_optional:
        unavailable_qty = sum(unavailable_optional.values())
        print(f"\n   Note: {unavailable_qty} optional card copy/copies not available:")
        for card in _format_card_count_list(unavailable_optional):
            print(f"     - {card}")
    
    if unavailable_mandatory or unavailable_optional:
        available_mandatory_total = sum(available_mandatory_qty.values())
        available_optional_total = sum(available_optional_qty.values())
        print(
            f"\n   Optimising for {available_mandatory_total} mandatory + "
            f"{available_optional_total} optional card copy/copies...\n"
        )
    
    # Validate tag constraints against available cards
    if tag_constraints:
        print("\n   Validating tag constraints...")
        validate_tag_constraints(
            tag_constraints,
            card_tags,
            available_mandatory_qty,
            available_optional_qty,
        )
    
    # Create problem
    model = pulp.LpProblem("MTG_Min_Cost", pulp.LpMinimize)
    
    # Decision variables
    z = pulp.LpVariable.dicts(
        "z", [(v, c) for v in vendors for c in cards],
        lowBound=0,
        cat="Integer"
    )
    
    x = pulp.LpVariable.dicts(
        "x", vendors,
        cat="Binary"
    )
    
    # Decision variable for optional quantity selected per card
    y = pulp.LpVariable.dicts(
        "y", list(available_optional_qty),
        lowBound=0,
        cat="Integer"
    )
    
    # Objective function
    model += (
        pulp.lpSum(K[v, c] * z[v, c] for v in vendors for c in cards)
        + pulp.lpSum(shipping_costs.get(v, 0) * x[v] for v in vendors)
        + vendor_penalty * pulp.lpSum(x[v] for v in vendors)
    )
    
    # Constraints: Each mandatory card bought for its required quantity
    for c, qty in available_mandatory_qty.items():
        model += pulp.lpSum(z[v, c] for v in vendors) == qty

    # Constraints: Optional card quantity is chosen up to configured quantity
    for c, qty in available_optional_qty.items():
        model += pulp.lpSum(z[v, c] for v in vendors) == y[c]
        model += y[c] <= qty
    
    # Constraint: Minimum number of optional cards must be purchased
    if available_optional_qty and min_optional_cards > 0:
        max_optional_available = sum(available_optional_qty.values())
        actual_min = min(min_optional_cards, max_optional_available)
        model += pulp.lpSum(y[c] for c in available_optional_qty) >= actual_min
    
    # Tag constraints
    if tag_constraints:
        add_tag_constraints(
            model,
            tag_constraints,
            card_tags,
            available_mandatory_qty,
            available_optional_qty,
            y,
        )
    
    # Linking constraint: can only buy from vendor if we use that vendor
    for v in vendors:
        for c in cards:
            max_qty_for_card = available_mandatory_qty.get(c, 0) + available_optional_qty.get(c, 0)
            model += z[v, c] <= max_qty_for_card * x[v]
    
    # Solve
    print("\nSolving optimisation problem...")
    solver_candidates = _build_solver_candidates()
    solve_errors = []
    solved = False
    for solver_name, solver in solver_candidates:
        try:
            model.solve(solver)
            solved = True
            break
        except (OSError, pulp.PulpSolverError) as e:
            solve_errors.append(f"{solver_name}: {e}")

    if not solved:
        attempted = ", ".join(name for name, _ in solver_candidates)
        details = "\n   - ".join(solve_errors) if solve_errors else "No solver candidates were available."
        raise ValueError(
            "No compatible MILP solver could be executed.\n"
            f"   Attempted: {attempted if attempted else 'none'}\n"
            f"   - {details}\n"
            "   On Apple Silicon macOS, install native CBC with `brew install cbc`.\n"
            "   On Windows, the bundled PuLP CBC solver should work in a standard 64-bit Python environment."
        )
    
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
    
    return (
        model,
        x,
        z,
        y,
        vendors,
        cards,
        K,
        unavailable_cards,
        available_mandatory_qty,
        available_optional_qty,
    )


def save_results(
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
    output_file="results.txt",
):
    """Save optimisation results to file."""
    total_cost = 0
    mandatory_purchased = 0
    optional_purchased = 0
    
    with open(output_file, "w") as f:
        f.write(f"Status: {pulp.LpStatus[model.status]}\n\n")
        
        for v in sorted(vendors):
            purchased_cards = [c for c in cards if int(round(z[v, c].value() or 0)) > 0]

            if not purchased_cards:
                continue  # Skip vendor entirely if no cards bought

            if x[v].value() == 1:
                vendor_total = shipping_costs.get(v, 0)  # Start with shipping cost
                f.write(f"Use vendor: {v} (shipping: ${shipping_costs.get(v, 0):.2f})\n")
                
                for c in sorted(cards):
                    qty = int(round(z[v, c].value() or 0))
                    if qty > 0:
                        price = float(K[(v, c)])
                        line_total = qty * price
                        vendor_total += line_total
                        is_optional = c in optional_card_quantities
                        card_type = " [OPTIONAL]" if is_optional else ""
                        qty_prefix = f"{qty}x " if qty > 1 else ""
                        f.write(
                            f"  Buy {qty_prefix}{c} at ${price:.2f} each "
                            f"(line total: ${line_total:.2f}){card_type}\n"
                        )
                        
                        if is_optional:
                            optional_purchased += qty
                        else:
                            mandatory_purchased += qty
                
                total_cost += vendor_total
                f.write(f"  Subtotal for {v}: ${vendor_total:.2f}\n\n")
        
        f.write(f"Total cost (including shipping): ${total_cost:.2f}\n")
        f.write(f"Cards purchased: {mandatory_purchased} mandatory, {optional_purchased} optional\n")
        
        optional_not_purchased = {}
        for card, requested_qty in optional_card_quantities.items():
            purchased_qty = int(round(y[card].value() or 0))
            missing_qty = requested_qty - purchased_qty
            if missing_qty > 0:
                optional_not_purchased[card] = missing_qty
        
        if optional_not_purchased:
            f.write(f"\n" + "=" * 60 + "\n")
            total_missing = sum(optional_not_purchased.values())
            f.write(f"OPTIONAL CARDS NOT PURCHASED ({total_missing}):")
            f.write(f"\nThe following optional cards were available but not selected by the optimiser:\n\n")
            for card in _format_card_count_list(optional_not_purchased):
                f.write(f"  - {card}\n")
        
        if unavailable_cards:
            f.write(f"\n" + "=" * 60 + "\n")
            total_unavailable = sum(unavailable_cards.values())
            f.write(f"UNAVAILABLE CARDS ({total_unavailable}):")
            f.write(f"\nThe following cards were not available from any vendor:\n\n")
            for card in _format_card_count_list(unavailable_cards):
                f.write(f"  - {card}\n")
    
    print(f"\nResults saved to {output_file}")
    print(f"Total cost: ${total_cost:.2f}")
    optional_requested_total = sum(optional_card_quantities.values())
    print(
        f"Cards purchased: {mandatory_purchased} mandatory, "
        f"{optional_purchased}/{optional_requested_total} optional"
    )
    if optional_not_purchased:
        print(f"Optional cards not purchased: {sum(optional_not_purchased.values())}")
    if unavailable_cards:
        print(f"Unavailable cards: {sum(unavailable_cards.values())}")
