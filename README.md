# Card Optimiser

Optimises bulk purchases from the website mtgsingles.co.nz, allowing you to make bulk orders and automatically determine where to order cards from to minimise costs.

## Usage

1. Configure your cards and vendors in `config.yaml`
2. Run `python run_optimiser.py`
3. View results in the `results/` folder

## Flask GUI

You can also run a browser GUI:

1. Install Flask (if not already installed): `pip install flask`
2. Start the app: `python app.py`
3. Open `http://127.0.0.1:5000`

The GUI lets you choose:
- Pickup cities
- Stores/vendors
- Mandatory and optional cards
- Card tags (chip-based selector)
- Tag constraints

## Configuration

Edit `config.yaml` to set:
- Card list
- Vendor list
- Shipping costs
- Vendor penalty
- Optional cards and minimums
- Card tags and tag constraints

### Card Tagging (Optional)

You can add tags to cards to control how many of each type are selected:

```yaml
optional_cards:
  - Carrion Feeder [black, sacrifice]
  - Arcbound Mouser [artifact]

tag_constraints:
  black:
    minimum: 5    # At least 5 black cards
    maximum: 10   # At most 10 black cards
  sacrifice:
    target: 3     # Exactly 3 sacrifice cards
```

The optimizer will automatically validate constraints and report errors if they cannot be satisfied.

## Requirements

- Python 3.x
- PuLP (optimisation)
- PyYAML
- requests/BeautifulSoup (price scraping)
