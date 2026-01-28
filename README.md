# Card Optimiser

Optimises bulk purchases from the website mtgsingles.co.nz, allowing you to make bulk orders and automatically determine where to order cards from to minimise costs.

## Usage

1. Configure your cards and vendors in `config.yaml`
2. Run `python run_optimiser.py`
3. View results in the `results/` folder

## Configuration

Edit `config.yaml` to set:
- Card list
- Vendor list
- Shipping costs
- Vendor penalty
- Optional cards and minimums

## Requirements

- Python 3.x
- PuLP (optimisation)
- PyYAML
- requests/BeautifulSoup (price scraping)
