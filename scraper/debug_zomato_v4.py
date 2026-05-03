# scraper/debug_zomato_v4.py
# Key insight: cookies only set after hitting a real Zomato page (even a 404)
# Use those cookies + csrf for all webroute calls
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_v4.py

import asyncio
import sys
import json
import gzip
import httpx

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

LAT, LNG = 12.9352, 77.6245
KEYWORD  = "biryani"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}


def make_api_headers(csrf: str, referer: str) -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Referer": referer,
        "Origin": "https://www.zomato.com",
        "x-zomato-csrft": csrf,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def safe_json(r: httpx.Response, label: str = "") -> dict | None:
    try:
        return r.json()
    except Exception:
        pass
    try:
        return json.loads(r.content.decode("utf-8", errors="replace"))
    except Exception:
        pass
    try:
        return json.loads(gzip.decompress(r.content).decode("utf-8"))
    except Exception:
        pass
    if HAS_BROTLI:
        try:
            return json.loads(brotli.decompress(r.content).decode("utf-8"))
        except Exception:
            pass
    if label:
        with open(f"zomato_{label}.bin", "wb") as f:
            f.write(r.content)
        print(f"  [raw bytes saved -> zomato_{label}.bin, hex: {r.content[:16].hex()}]")
    return None


def is_real(d: dict) -> bool:
    """Return True if response is real data, not Zomato's fake-200 404 page."""
    fsd = d.get("page_data", {}).get("firstSectionData", {})
    return "can't seem" not in str(fsd.get("text", ""))


async def probe(client: httpx.AsyncClient, url: str, headers: dict, label: str) -> dict | None:
    """GET url, decode, check for fake 404, return data or None."""
    try:
        r = await client.get(url, headers=headers)
        enc = r.headers.get("content-encoding", "none")
        ct  = r.headers.get("content-type", "")[:40]
        print(f"   {r.status_code} [{enc}] {ct}  <- {url[40:90]}")
        if r.status_code not in (200, 201):
            return None
        d = safe_json(r, label)
        if d is None:
            return None
        if not is_real(d):
            print("   -> fake-200 (404 page)")
            return None
        print(f"   -> REAL DATA! keys={list(d.keys())[:8]}")
        return d
    except Exception as e:
        print(f"   ERROR: {e}")
        return None


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:

        # ── Step 1: seed cookies via homepage ────────────────────────────────
        print("[1] Seeding session via homepage...")
        await client.get("https://www.zomato.com", headers=BROWSER_HEADERS)
        # cookies come after the 404 redirect page
        await client.get("https://www.zomato.com/bangalore", headers=BROWSER_HEADERS)
        cookies = dict(client.cookies)
        csrf = cookies.get("csrf", cookies.get("csrft", ""))
        print(f"[1] Cookies: {list(cookies.keys())}")
        print(f"[1] csrf: '{csrf}'")

        api_h = make_api_headers(csrf, "https://www.zomato.com/bangalore")

        # ── Step 2: probe ALL known Zomato food URL patterns ─────────────────
        print("\n[2] Probing Zomato food delivery URL patterns...")
        BASE = "https://www.zomato.com/webroutes/getPage?page_url="
        paths = [
            "%2Forder",                                      # generic /order
            "%2Fbangalore%2Forder",                          # /bangalore/order
            "%2Fbangalore%2Ffood-delivery",                  # /bangalore/food-delivery
            "%2Fbangalore%2Fdelivery",                       # /bangalore/delivery
            "%2Fbangalore%2Ffood",                           # /bangalore/food
            "%2Ffood-delivery%2Fbangalore",                  # /food-delivery/bangalore
            "%2Ffood-delivery%2Fbengaluru",                  # bengaluru spelling
            "%2Fbengaluru%2Forder",                          # bengaluru/order
            "%2Fbangalore%2Fonline-food-delivery",           # /online-food-delivery
        ]
        real_data = None
        for path in paths:
            url = f"{BASE}{path}&isMobile=0"
            d = await probe(client, url, api_h, f"path_{path[:20]}")
            if d:
                real_data = d
                pd = d.get("page_data", {})
                print(f"   page_data keys: {list(pd.keys())[:10]}")
                # Look for sections with restaurant lists
                for sk in ["sections", "cards", "restaurants", "listing"]:
                    if sk in pd:
                        v = pd[sk]
                        print(f"   page_data.{sk} type={type(v).__name__} ", end="")
                        print(f"len={len(v)}" if isinstance(v, (list, dict)) else str(v)[:40])
                with open("zomato_real.json", "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                print("   Saved -> zomato_real.json")
                break

        # ── Step 3: try webroutes/user/food API ──────────────────────────────
        print("\n[3] Probing Zomato direct API routes...")
        api_urls = [
            f"https://www.zomato.com/webroutes/delivery/getDeliveryPage?lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/restaurants/search?q={KEYWORD}&lat={LAT}&lng={LNG}&context=delivery",
            f"https://www.zomato.com/webroutes/city/getSections?lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/delivery/listing?lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Forder%3Flat%3D{LAT}%26lng%3D{LNG}&isMobile=0",
        ]
        for url in api_urls:
            d = await probe(client, url, api_h, "api")
            if d:
                with open("zomato_api_real.json", "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                print("   Saved -> zomato_api_real.json")
                break

        # ── Step 4: try the location cookie approach ──────────────────────────
        print("\n[4] Setting location cookie and retrying...")
        # Zomato location cookie format
        loc_cookie = f"lat%3D{LAT}%26lng%3D{LNG}%26cityId%3D4%26cityName%3DBangalore%26locality%3D"
        client.cookies.set("userLocation", loc_cookie, domain=".zomato.com")
        client.cookies.set("zl", loc_cookie, domain=".zomato.com")

        d4 = await probe(
            client,
            f"{BASE}%2Fbangalore%2Forder&isMobile=0",
            make_api_headers(csrf, "https://www.zomato.com/bangalore/order"),
            "loc_cookie"
        )
        if d4:
            with open("zomato_loc.json", "w", encoding="utf-8") as f:
                json.dump(d4, f, indent=2, ensure_ascii=False)
            print("   Saved -> zomato_loc.json")

        # ── Step 5: summary ────────────────────────────────────────────────
        print(f"\n[5] brotli: {HAS_BROTLI} | httpx: {httpx.__version__}")
        if not real_data:
            print("\n[!] All paths returned fake-200 or errors.")
            print("    This means Zomato is geo-blocking non-Indian IPs at the webroute level.")
            print("    Options:")
            print("    A) Use a VPN set to India and retry")
            print("    B) Use Playwright with stealth plugin (harder to block)")
            print("    C) Use Zomato's official Partner API (requires registration)")
            print("    D) Accept Swiggy-only for MVP, add Zomato later")
        print("\n[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
