"""
scraper/debug_zomato_dump.py
Run once to dump the raw 'info' dict of the first Zomato restaurant result.
This reveals the exact keys for delivery_time and price_for_two.

Usage:
    python scraper/debug_zomato_dump.py
"""

import asyncio
import json
import httpx
import pathlib

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_BANGALORE_LOC = {
    "latitude": "12.9716060000000000",
    "longitude": "77.5943760000000000",
    "userDefinedLatitude": 12.971606,
    "userDefinedLongitude": 77.594376,
    "cityId": 4,
    "cityName": "Bengaluru",
    "countryId": 1,
    "countryName": "India",
    "entityId": 4,
    "entityType": "city",
    "locationType": "poi",
    "addressId": 0,
    "isOrderLocation": 1,
    "entityName": "Table Space UB City, Bengaluru",
    "orderLocationName": "Table Space UB City, Bengaluru",
    "displayTitle": "UB City",
    "o2Serviceable": True,
    "placeId": "3655",
    "cellId": "4300399395616063488",
    "deliverySubzoneId": 3655,
    "placeType": "DSZ",
    "placeName": "Table Space UB City, Bengaluru",
    "isO2City": True,
    "fetchFromGoogle": False,
    "fetchedFromCookie": False,
    "isO2OnlyCity": False,
    "address_template": [],
    "otherRestaurantsUrl": "",
}


def _make_filters():
    prev_search = json.dumps({
        "PreviousSearchFilter": [
            json.dumps({"category_context": "delivery_home"}),
            "",
        ]
    })
    postback = json.dumps({"processed_chain_ids": [], "shown_res_count": 0})
    return json.dumps({
        "searchMetadata": {
            "previousSearchParams": prev_search,
            "postbackParams": postback,
            "totalResults": 1374,
            "hasMore": True,
            "getInactive": False,
        },
        "dineoutAdsMetaData": {},
        "appliedFilter": [{
            "filterType": "category_sheet",
            "filterValue": "delivery_home",
            "isHidden": True,
            "isApplied": True,
            "postKey": json.dumps({"category_context": "delivery_home"}),
        }],
        "urlParamsForAds": {},
    })


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        seed_h = {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-IN",
        }
        await client.get("https://www.zomato.com", headers=seed_h)
        await client.get("https://www.zomato.com/bangalore", headers=seed_h)
        cr = await client.get(
            "https://www.zomato.com/webroutes/auth/csrf",
            headers={"User-Agent": BROWSER_UA, "Accept": "application/json",
                     "Referer": "https://www.zomato.com/bangalore/delivery"}
        )
        csrf = cr.json().get("csrf", client.cookies.get("csrf", ""))
        print(f"csrf: {csrf[:20]}...")

        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IN",
            "Content-Type": "application/json",
            "Referer": "https://www.zomato.com/bangalore/delivery",
            "Origin": "https://www.zomato.com",
            "x-zomato-csrft": csrf,
        }

        payload = {"context": "delivery", "filters": _make_filters(), **_BANGALORE_LOC}
        r = await client.post(
            "https://www.zomato.com/webroutes/search/home",
            headers=headers,
            json=payload,
        )
        print(f"HTTP {r.status_code}")
        data = r.json()

        sr = data.get("sections", {}).get("SECTION_SEARCH_RESULT", [])
        print(f"SECTION_SEARCH_RESULT items: {len(sr)}")

        if not sr:
            pathlib.Path("zomato_full_response.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8"
            )
            print("No results - full response saved to zomato_full_response.json")
            return

        # Dump raw item[0] — use ensure_ascii=True to avoid cp1252 issues on Windows
        item = sr[0]
        info = item.get("info") or item

        pathlib.Path("zomato_info_sample.json").write_text(
            json.dumps(info, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        print("\n=== zomato_info_sample.json written ===")
        print(f"Top-level keys: {list(info.keys())}")

        # Print any key that looks like eta/price/cost/delivery/time
        keywords = ("eta", "price", "cost", "delivery", "time")
        print("\n--- Relevant keys (name + value) ---")
        for k, v in info.items():
            if any(kw.lower() in k.lower() for kw in keywords):
                # encode to ascii for safe Windows console output
                safe_v = json.dumps(v, ensure_ascii=True)[:120]
                print(f"  {k!r}: {safe_v}")

        # Also check one level deep
        print("\n--- Nested relevant keys ---")
        for k, v in info.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if any(kw.lower() in kk.lower() for kw in keywords):
                        safe_v = json.dumps(vv, ensure_ascii=True)[:120]
                        print(f"  info[{k!r}][{kk!r}]: {safe_v}")


asyncio.run(main())
