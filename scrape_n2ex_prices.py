"""
Scrape N2EX auction prices from the Nord Pool Data Portal (SPA).
Depends on portal DOM: price rows in a MUI DataGrid (role="row", cells with data fields).
If the layout changes, update SELECTORS below.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_PATH = "/auction/n2ex/prices"
# Template URL (defaults for CLI). Query is rebuilt from argparse; override any piece with flags.
DEFAULT_PORTAL_URL = (
    "https://data.nordpoolgroup.com/auction/n2ex/prices"
    "?deliveryDate=2026-04-06&currency=GBP&aggregation=DeliveryPeriod&deliveryAreas=UK"
)
NAV_TIMEOUT_MS = 60_000
GRID_TIMEOUT_MS = 45_000


@dataclass
class QueryParams:
    delivery_date: str
    currency: str
    aggregation: str
    delivery_areas: str

    def to_dict(self) -> dict[str, str]:
        return {
            "deliveryDate": self.delivery_date,
            "currency": self.currency,
            "aggregation": self.aggregation,
            "deliveryAreas": self.delivery_areas,
        }


def build_portal_url(params: QueryParams) -> str:
    q = urlencode(params.to_dict())
    return f"https://data.nordpoolgroup.com{BASE_PATH}?{q}"


def parse_portal_url(url: str) -> QueryParams:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    def one(key: str, default: str | None = None) -> str:
        v = qs.get(key, [default] if default is not None else [])
        if not v or v[0] is None or v[0] == "":
            raise SystemExit(f"URL missing query parameter: {key}")
        return v[0]
    return QueryParams(
        delivery_date=one("deliveryDate"),
        currency=one("currency", "GBP"),
        aggregation=one("aggregation", "DeliveryPeriod"),
        delivery_areas=one("deliveryAreas", "UK"),
    )


_DEFAULT_PARAMS = parse_portal_url(DEFAULT_PORTAL_URL)


def accept_cookies_if_present(page) -> None:
    # Cookie banner: buttons like "Allow and close" / "Allow"
    for name in ("Allow and close", "Allow", "Accept all"):
        btn = page.get_by_role("button", name=re.compile(re.escape(name), re.I))
        try:
            if btn.count() and btn.first.is_visible(timeout=2000):
                btn.first.click()
                return
        except PlaywrightTimeoutError:
            continue


def scrape_rows_from_grid(page) -> list[dict[str, Any]]:
    """
    MUI DataGrid: rows have role='row' and cells often expose data-field.
    Skip the header row (columnheader cells).
    """
    page.wait_for_selector('[role="grid"]', timeout=GRID_TIMEOUT_MS)
    page.wait_for_selector('[role="row"] [role="gridcell"]', timeout=GRID_TIMEOUT_MS)

    return page.evaluate(
        """() => {
  const grid = document.querySelector('[role="grid"]');
  if (!grid) return [];
  const rows = Array.from(grid.querySelectorAll('[role="row"]'));
  const out = [];
  for (const row of rows) {
    if (row.querySelector('[role="columnheader"]')) continue;
    const cells = Array.from(row.querySelectorAll('[role="gridcell"]'));
    const rec = {};
    for (let i = 0; i < cells.length; i++) {
      const cell = cells[i];
      const field = cell.getAttribute("data-field") || cell.getAttribute("data-colindex");
      let text = (cell.innerText || "").trim().replace(/\\s+/g, " ");
      if (field) rec[field] = text;
      else if (i === 0) rec["period"] = text;
      else if (i === 1) rec["price"] = text;
      else rec["col_" + i] = text;
    }
    if (Object.keys(rec).length) out.push(rec);
  }
  return out;
}"""
    )


def parse_portal_price(value: Any) -> float | None:
    """Portal shows decimals with a comma (e.g. 89,20). JSON uses float or null."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s in ("-", "—", "N/A", "n/a"):
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def rows_with_float_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        if "price" in r:
            r["price"] = parse_portal_price(r["price"])
        out.append(r)
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Scrape N2EX prices from Nord Pool Data Portal. "
            "Default query matches DEFAULT_PORTAL_URL in this file; override with flags."
        ),
    )
    p.add_argument(
        "--url",
        help="Use this full portal URL instead of building from DEFAULT_PORTAL_URL + flags.",
    )
    p.add_argument(
        "--delivery-date",
        dest="delivery_date",
        default=_DEFAULT_PARAMS.delivery_date,
        help=f"deliveryDate query param (default: {_DEFAULT_PARAMS.delivery_date})",
    )
    p.add_argument(
        "--currency",
        default=_DEFAULT_PARAMS.currency,
        help=f"(default: {_DEFAULT_PARAMS.currency})",
    )
    p.add_argument(
        "--aggregation",
        default=_DEFAULT_PARAMS.aggregation,
        help=f"Hourly or DeliveryPeriod (default: {_DEFAULT_PARAMS.aggregation})",
    )
    p.add_argument(
        "--delivery-areas",
        default=_DEFAULT_PARAMS.delivery_areas,
        help=f"(default: {_DEFAULT_PARAMS.delivery_areas})",
    )
    p.add_argument("--output", "-o", help="Write JSON to this file instead of stdout.")
    p.add_argument("--headed", action="store_true", help="Show browser window (debug).")
    p.add_argument(
        "--use-edge",
        action="store_true",
        help="Use installed Microsoft Edge (no 'playwright install chromium' needed on Windows).",
    )
    args = p.parse_args()

    if args.url:
        portal_url = args.url.strip()
        if not portal_url.startswith("http"):
            portal_url = "https://" + portal_url.lstrip("/")
        params = parse_portal_url(portal_url)
    else:
        params = QueryParams(
            delivery_date=args.delivery_date,
            currency=args.currency,
            aggregation=args.aggregation,
            delivery_areas=args.delivery_areas,
        )
        portal_url = build_portal_url(params)

    payload: dict[str, Any] = {
        "url": portal_url,
        "query": params.to_dict(),
        "rows": [],
    }

    with sync_playwright() as pw:
        launch_kwargs: dict[str, Any] = {"headless": not args.headed}
        if args.use_edge:
            launch_kwargs["channel"] = "msedge"
        try:
            browser = pw.chromium.launch(**launch_kwargs)
        except Exception as e:
            if not args.use_edge and "Executable doesn't exist" in str(e):
                raise SystemExit(
                    "Playwright browser not installed. Run: .\\.venv\\Scripts\\playwright install chromium\n"
                    "Or re-run with --use-edge to use Microsoft Edge."
                ) from e
            raise
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        page = context.new_page()
        try:
            page.goto(portal_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            accept_cookies_if_present(page)
            page.wait_for_load_state("networkidle", timeout=GRID_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass

        try:
            rows = scrape_rows_from_grid(page)
        except PlaywrightTimeoutError as e:
            browser.close()
            raise SystemExit(
                "Timed out waiting for price grid. The portal layout may have changed; "
                "inspect scrape_n2ex_prices.py (MUI DataGrid selectors)."
            ) from e

        payload["rows"] = rows_with_float_prices(rows)
        browser.close()

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
