# Nord Pool Data Scraping

Temporary Python scraper for Nord Pool N2EX prices from the public data portal:

- URL pattern: `https://data.nordpoolgroup.com/auction/n2ex/prices?...`
- Source page is JS-rendered (SPA), so this uses Playwright.

## Requirements

- Python 3.11+
- Windows PowerShell
- Microsoft Edge installed (recommended for this project)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional if you want bundled Chromium instead of Edge:

```powershell
playwright install chromium
```

## Run

Use defaults embedded in script (example date/GBP/UK):

```powershell
python scrape_n2ex_prices.py --use-edge
```

Specify a full URL:

```powershell
python scrape_n2ex_prices.py --url "https://data.nordpoolgroup.com/auction/n2ex/prices?deliveryDate=2026-04-06&currency=GBP&aggregation=DeliveryPeriod&deliveryAreas=UK" --use-edge
```

Override individual args:

```powershell
python scrape_n2ex_prices.py --delivery-date 2026-04-07 --aggregation Hourly --delivery-areas UK --currency GBP --use-edge
```

Write to file:

```powershell
python scrape_n2ex_prices.py --delivery-date 2026-04-07 --use-edge -o output.json
```

## Output

JSON object with:

- `url`
- `query`
- `rows` (each row has `period` and `price`; `price` is converted to float)

## Prepare for GitHub

```powershell
git add .
git commit --trailer "Made-with: Cursor" -m "Initial scraper setup"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```
