"""
Web scraping services for sources without APIs.
- Matba Rofex (futuros financieros)
- Rava Bursátil (fallback)
- Bonistas (bonos)
- A Cuánto Está (cotizaciones)
"""
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


async def fetch_page(url: str) -> Optional[str]:
    """Fetch a web page and return its HTML content."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


# ──────────────────────────────────────────────
# MATBA ROFEX - Futuros Financieros
# ──────────────────────────────────────────────

async def fetch_matba_rofex_futures() -> list[dict]:
    """
    Fetch financial futures from Matba Rofex.
    Source: https://matbarofex.primary.ventures/fyo/futurosfinancieros
    Note: This page may use JS rendering. If scraping fails, we fallback to
    their API if one is discovered.
    """
    url = "https://matbarofex.primary.ventures/fyo/futurosfinancieros"
    html = await fetch_page(url)
    if not html:
        return []

    futures = []
    try:
        soup = BeautifulSoup(html, "lxml")
        # Try to find the data table — structure may vary
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = row.find_all("td")
                if len(cells) >= 4:
                    futures.append({
                        "contract": cells[0].get_text(strip=True),
                        "last": cells[1].get_text(strip=True),
                        "change": cells[2].get_text(strip=True),
                        "volume": cells[3].get_text(strip=True),
                    })
    except Exception as e:
        logger.error(f"Error parsing Matba Rofex: {e}")

    # Also try the API endpoint (Primary uses a REST API internally)
    api_url = "https://matbarofex.primary.ventures/api/futuros"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(api_url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
    except Exception:
        pass

    logger.info(f"Fetched {len(futures)} futures from Matba Rofex (scraping)")
    return futures


# ──────────────────────────────────────────────
# BONISTAS.COM
# ──────────────────────────────────────────────

async def fetch_bonistas_data() -> list[dict]:
    """Fetch bond data from bonistas.com."""
    url = "https://bonistas.com/"
    html = await fetch_page(url)
    if not html:
        return []

    bonds = []
    try:
        soup = BeautifulSoup(html, "lxml")
        # Look for bond tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    bonds.append({
                        "name": cells[0].get_text(strip=True),
                        "price": cells[1].get_text(strip=True),
                        "yield": cells[2].get_text(strip=True) if len(cells) > 2 else None,
                    })
    except Exception as e:
        logger.error(f"Error parsing bonistas.com: {e}")

    logger.info(f"Fetched {len(bonds)} bonds from bonistas.com")
    return bonds


# ──────────────────────────────────────────────
# A CUÁNTO ESTÁ
# ──────────────────────────────────────────────

async def fetch_acuantoesta() -> dict:
    """Fetch dollar and other rates from acuantoesta.com.ar."""
    url = "https://www.acuantoesta.com.ar/"
    html = await fetch_page(url)
    if not html:
        return {}

    rates = {}
    try:
        soup = BeautifulSoup(html, "lxml")
        # Look for rate containers
        items = soup.find_all(class_=lambda c: c and ("cotizacion" in c.lower() or "rate" in c.lower()))
        for item in items:
            title = item.find(class_=lambda c: c and "title" in c.lower())
            value = item.find(class_=lambda c: c and ("value" in c.lower() or "precio" in c.lower()))
            if title and value:
                rates[title.get_text(strip=True)] = value.get_text(strip=True)
    except Exception as e:
        logger.error(f"Error parsing acuantoesta.com.ar: {e}")

    # Also try to find their API
    api_candidates = [
        "https://www.acuantoesta.com.ar/api/cotizaciones",
        "https://www.acuantoesta.com.ar/api/v1/dolar",
    ]
    for api_url in api_candidates:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(api_url, headers=HEADERS)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return {"api_data": data, "scraped": rates}
        except Exception:
            continue

    return rates


# ──────────────────────────────────────────────
# RAVA BURSÁTIL (fallback)
# ──────────────────────────────────────────────

async def fetch_rava_precios() -> list[dict]:
    """Fetch stock prices from Rava Bursátil (fallback source)."""
    url = "https://www.rava.com/empresas/perfil.php?e=panel"
    html = await fetch_page(url)
    if not html:
        return []

    stocks = []
    try:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", class_=lambda c: c and "tabla" in c.lower()) or soup.find("table")
        if table:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) >= 5:
                    stocks.append({
                        "ticker": cells[0].get_text(strip=True),
                        "last": cells[1].get_text(strip=True),
                        "change_pct": cells[2].get_text(strip=True),
                        "volume": cells[3].get_text(strip=True),
                        "time": cells[4].get_text(strip=True),
                    })
    except Exception as e:
        logger.error(f"Error parsing Rava: {e}")

    logger.info(f"Fetched {len(stocks)} stocks from Rava")
    return stocks
