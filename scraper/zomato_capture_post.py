# scraper/zomato_capture_post.py
# Captures the EXACT POST payload + request headers Zomato sends to
# /webroutes/search/home so we can replicate it in httpx.
#
# Run: .\venv\Scripts\python.exe scraper\zomato_capture_post.py

import asyncio
import json
import sys
from playwright.async_api import async_playwright

TARGET_URL = "https://www.zomato.com/bangalore/delivery"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": 12.9352, "longitude": 77.6245},
            permissions=["geolocation"],
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        captured = []

        # Intercept REQUESTS (not responses) to get the POST body
        async def on_request(request):
            if "search/home" in request.url:
                try:
                    post_data = request.post_data
                    headers   = dict(request.headers)
                    print(f"\n[REQUEST] POST {request.url}")
                    print(f"  headers: {json.dumps(headers, indent=2)[:800]}")
                    print(f"  body: {post_data[:500] if post_data else 'None'}")
                    captured.append({
                        "url":     request.url,
                        "method":  request.method,
                        "headers": headers,
                        "body":    post_data,
                    })
                except Exception as e:
                    print(f"  [capture error] {e}")

        # Also intercept responses to confirm we get data
        async def on_response(response):
            if "search/home" in response.url:
                try:
                    body = await response.text()
                    print(f"\n[RESPONSE] {response.status} {response.url}")
                    print(f"  body[:300]: {body[:300]}")
                    # Save full response
                    idx = len(captured)
                    with open(f"zomato_home_response_{idx}.json", "w", encoding="utf-8") as f:
                        f.write(body)
                    print(f"  Saved -> zomato_home_response_{idx}.json")
                except Exception as e:
                    print(f"  [response error] {e}")

        page.on("request",  on_request)
        page.on("response", on_response)

        print(f"[1] Loading {TARGET_URL} ...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        print("[2] Scrolling to trigger search/home calls...")
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(2)

        await asyncio.sleep(3)

        if captured:
            with open("zomato_post_capture.json", "w", encoding="utf-8") as f:
                json.dump(captured, f, indent=2, ensure_ascii=False)
            print(f"\nSaved {len(captured)} captured requests -> zomato_post_capture.json")
            print("\n=== PAYLOADS ===")
            for c in captured:
                print(f"  {c['body']}")
        else:
            print("[!] Nothing captured for search/home.")

        await browser.close()
        print("[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    else:
        asyncio.run(main())
