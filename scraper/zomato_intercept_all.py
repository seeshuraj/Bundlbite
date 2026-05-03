# scraper/zomato_intercept_all.py
# Logs ALL network responses while loading Zomato delivery page.
# Helps identify the exact XHR endpoint for restaurant listings.
#
# Run: .\venv\Scripts\python.exe scraper\zomato_intercept_all.py

import asyncio
import json
import sys
from playwright.async_api import async_playwright

LAT = 12.9352
LNG = 77.6245
TARGET_URL = "https://www.zomato.com/bangalore/delivery"

all_requests = []   # (url, status, content-type, body_snippet)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": LAT, "longitude": LNG},
            permissions=["geolocation"],
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        async def on_response(response):
            url = response.url
            # Skip static assets
            if any(ext in url for ext in [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico"]):
                return
            status = response.status
            ct = response.headers.get("content-type", "")[:60]

            body_snippet = ""
            if "json" in ct or "text" in ct:
                try:
                    text = await response.text()
                    body_snippet = text[:200].replace("\n", " ")
                except Exception:
                    body_snippet = "[read error]"

            entry = {
                "url": url,
                "status": status,
                "ct": ct,
                "body": body_snippet,
            }
            all_requests.append(entry)
            # Print JSON responses immediately
            if "json" in ct:
                print(f"[JSON] {status} {url[:100]}")
                print(f"       {body_snippet[:120]}")

        page.on("response", on_response)

        print(f"[1] Loading {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        print("[2] Scrolling...")
        for _ in range(6):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(2)

        await asyncio.sleep(4)

        print(f"\n[3] Total non-asset responses captured: {len(all_requests)}")

        # Save full log
        with open("zomato_network_log.json", "w", encoding="utf-8") as f:
            json.dump(all_requests, f, indent=2, ensure_ascii=False)
        print("Saved -> zomato_network_log.json")

        # Print summary of all JSON hits
        print("\n=== All JSON responses ===")
        for r in all_requests:
            if "json" in r["ct"]:
                print(f"  [{r['status']}] {r['url'][:120]}")

        await browser.close()
        print("[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        asyncio.run(main())
