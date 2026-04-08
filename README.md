# Nord Pool N2EX Price Scraper

Python scraper for N2EX prices from the Nord Pool data portal:

- Endpoint pattern: `https://data.nordpoolgroup.com/auction/n2ex/prices?...`
- Source page is a JavaScript SPA, so scraping is done with Playwright.
- Output is CSV (hourly by default, optional half-hourly expansion).

## What This Script Produces

The script writes market prices with normalized naming:

- `start_dt` - timezone-aware start datetime in `Europe/London`
- `deliverydate` - delivery date used for market records
- `start_t` - settlement start time (`HH:MM`)
- `price_gbp_mwh` - numeric price
- `settlement_period` - only included when `--half-hourly` is enabled

## Requirements

- Python 3.11+
- Windows PowerShell
- Microsoft Edge installed (recommended)

Dependencies are installed from `requirements.txt`:

- `playwright`
- `tzdata` (required for `Europe/London` timezone resolution on Windows)
- `openpyxl` (required for Excel `.xlsx` pivot export)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you prefer bundled Chromium instead of Edge:

```powershell
.\.venv\Scripts\playwright install chromium
```

## Usage

### Quick Start (defaults from script)

```powershell
python scrape_n2ex_prices.py --use-edge -o prices_hourly.csv
```

### Hourly output

```powershell
python scrape_n2ex_prices.py `
  --delivery-date 2026-04-08 `
  --aggregation Hourly `
  --delivery-areas UK `
  --currency GBP `
  --use-edge `
  -o prices_hourly.csv
```

### Half-hourly output

```powershell
python scrape_n2ex_prices.py `
  --delivery-date 2026-04-08 `
  --aggregation Hourly `
  --delivery-areas UK `
  --currency GBP `
  --use-edge `
  --half-hourly `
  -o prices_halfhourly.csv
```

### Example: half_hourly and `prices_pivot.xlsx` outputs

```powershell
python scrape_n2ex_prices.py `
  --delivery-date 2026-04-08 `
  --aggregation Hourly `
  --delivery-areas UK `
  --currency GBP `
  --use-edge `
  --half-hourly `
  -o prices_halfhourly.csv `
  --pivot-output prices_pivot.xlsx
```

This command creates:

- `prices_halfhourly.csv` (half-hourly rows)
- `prices_pivot.xlsx` (pivot table with `deliverydate` rows, `settlement_period` columns, and `price_gbp_mwh` values)

### One-command Python runner (no long CLI copy/paste)

If you do this often, run:

```powershell
python run_halfhourly_export.py
```

This wrapper loops through a date window (last 7 days through `+1` day), calls
`scrape_n2ex_prices.py` in half-hourly mode, and writes:

- `prices_halfhourly_window.csv`
- `prices_pivot.xlsx` (pivoted from the combined window dataset)

You can edit defaults in `run_halfhourly_export.py` (`days_back`, `days_forward`,
area, currency, and output filename).

### Use a full portal URL

```powershell
python scrape_n2ex_prices.py `
  --url "https://data.nordpoolgroup.com/auction/n2ex/prices?deliveryDate=2026-04-08&currency=GBP&aggregation=Hourly&deliveryAreas=UK" `
  --use-edge `
  -o prices.csv
```

## CLI Options

- `--url` full portal URL; if set, query params are read from the URL
- `--delivery-date` date for `deliveryDate` query param (format `YYYY-MM-DD`)
- `--currency` query currency (default from embedded template URL)
- `--aggregation` `Hourly` or `DeliveryPeriod` (default from embedded template URL)
- `--delivery-areas` area code such as `UK`
- `--output`, `-o` write CSV to file (otherwise writes CSV to stdout)
- `--half-hourly` duplicate each hourly row at `+30` minutes
- `--pivot-output` write pivoted Excel (`.xlsx`); requires `--half-hourly`
- `--use-edge` run Playwright with installed Microsoft Edge
- `--headed` run browser in headed mode for debugging

## Output Format

Expected row counts per delivery day:

- Hourly mode: 24 data rows
- Half-hourly mode: 48 data rows

### Hourly columns

- `start_dt`
- `deliverydate`
- `start_t`
- `price_gbp_mwh`

Example:

```csv
start_dt,deliverydate,start_t,price_gbp_mwh
2026-04-07T23:00+01:00,2026-04-07,23:00,89.78
2026-04-08T00:00+01:00,2026-04-08,00:00,93.11
```

### Half-hourly columns (`--half-hourly`)

- `start_dt`
- `deliverydate`
- `start_t`
- `settlement_period`
- `price_gbp_mwh`

Example:

```csv
start_dt,deliverydate,start_t,settlement_period,price_gbp_mwh
2026-04-07T23:00+01:00,2026-04-07,23:00,47,89.78
2026-04-07T23:30+01:00,2026-04-07,23:30,48,89.78
2026-04-08T00:00+01:00,2026-04-08,00:00,1,93.11
```

### Pivoted Excel format (`--pivot-output`)

- Sheet name: `prices_pivot`
- Row key: `deliverydate`
- Columns: `settlement_period` values (for example `1 ... 48`)
- Values: `price_gbp_mwh`

## Data Rules

- The script extracts the first time from portal periods (for example `23:00 - 00:00` -> `23:00`).
- If `start_t` is `23:00`, `deliverydate` is set to the previous day.
- Half-hourly mode adds a second row at `start_t + 30 minutes` and re-sorts by `deliverydate`, then `start_t`.
- `settlement_period` mapping in half-hourly mode is:
  - `00:00 -> 1`, `00:30 -> 2`, ..., `22:30 -> 46`, `23:00 -> 47`, `23:30 -> 48`
- `start_dt` is built from `deliverydate + start_t` in `Europe/London` and includes UTC offset.

## Troubleshooting

- If Playwright cannot find a browser:
  - use `--use-edge`, or
  - run `.\.venv\Scripts\playwright install chromium`
- If timezone data is missing:
  - run `python -m pip install -r requirements.txt` (installs `tzdata`)
- If scraping times out:
  - rerun with `--headed` to inspect page state
  - Nord Pool DOM changes may require selector updates in `scrape_n2ex_prices.py`

## Testing

Run all tests:

```powershell
.\.venv\Scripts\python -m unittest -v
```

Current suite (`test_scrape_n2ex_prices.py`) covers:

- delivery-date adjustment for `23:00`
- half-hourly expansion and sorting
- settlement period mapping and assignment
- London timezone datetime generation (`start_dt`) including BST/GMT offsets
- invalid datetime input handling
- portal price parsing edge cases (comma decimals, spaced thousands, null-like values)
- expected row counts (24 hourly, 48 half-hourly)
- exact output column order for hourly and half-hourly modes
- pivot matrix shape/content for Excel output
