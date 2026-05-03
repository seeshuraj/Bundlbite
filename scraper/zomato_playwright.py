# scraper/zomato_playwright.py
# Uses Playwright to open Zomato like a real browser, then intercepts
# the actual XHR/fetch calls that load restaurant listings.
#
# Install: pip install playwright && playwright install chromium
# Run:     .\venv\Scripts\python.exe scraper\zomato_playwright.py

import asyncio
import json
import sys
from playwright.async_api import async_playwright

LAT  = 12.9352
LNG  = 77.6245
TARGET_URL = "https://www.zomato.com/bangalore/delivery"

REST_URL_HINTS = ["getPage", "search", "delivery", "listing", "restaurant", "feed"]

captured = []


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": LAT, "longitude": LNG},
            permissions=["geolocation"],
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        async def handle_response(response):
            url = response.url
            ct  = response.headers.get("content-type", "")
            if "application/json" not in ct:
                return
            if not any(hint in url for hint in REST_URL_HINTS):
                return
            try:
                body = await response.json()
            except Exception:
                return

            sections = body.get("page_data", {}).get("sections", {})
            if isinstance(sections, dict):
                sr = sections.get("SECTION_SEARCH_RESULT", [])
                for sec in sr:
                    items = sec.get("items", [])
                    if items:
                        print(f"[XHR] RESTAURANT DATA FOUND!")
                        print(f"  URL: {url}")
                        print(f"  section type: {sec.get('type')}  items: {len(items)}")
                        info = items[0].get("info") or items[0]
                        print(f"  first restaurant: {info.get('name', '?')}")
                        captured.append({"url": url, "body": body})
                        fname = f"zomato_xhr_{len(captured)}.json"
                        with open(fname, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=2, ensure_ascii=False)
                        print(f"  Saved -> {fname}")
                        return

            if any(k in body for k in ["restaurants", "search_results", "results"]):
                print(f"[XHR] Possible alt endpoint: {url}")
                print(f"  keys: {list(body.keys())[:8]}")
                fname = f"zomato_alt_{len(captured)+1}.json"
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(body, f, indent=2, ensure_ascii=False)
                print(f"  Saved -> {fname}")
                captured.append({"url": url, "body": body})

        page.on("response", handle_response)

        print(f"[1] Navigating to {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        print("[2] Scrolling to trigger lazy loads...")
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1.5)

        await asyncio.sleep(3)

        print(f"\n[3] Captured {len(captured)} restaurant XHR responses.")
        if captured:
            print("\n=== Unique XHR URLs ===")
            for c in captured:
                print(f"  {c['url'][:120]}")
        else:
            print("[!] No restaurant XHRs captured. Waiting 15s for manual interaction...")
            await asyncio.sleep(15)
            print(f"    Captured after wait: {len(captured)}")

        await browser.close()
        print("[DONE]")


if __name__ == "__main__":
    # Windows requires ProactorEventLoop for subprocess (Playwright) support
    # Do NOT use WindowsSelectorEventLoopPolicy here — it blocks subprocess creation
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        asyncio.run(main())
