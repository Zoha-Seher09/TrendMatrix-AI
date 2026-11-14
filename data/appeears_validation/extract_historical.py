import csv
import json
import time
from pathlib import Path

import requests

BASE = "https://modis.ornl.gov/rst/api/v1"
LATITUDE = 31.58
LONGITUDE = 73.20
START = "2001-01-01"
END = "2025-12-31"

OUTPUT = Path("data/appeears_validation/historical_2001_2025")
OUTPUT.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    ("MOD13Q1", "250m_16_days_NDVI", 0.0001),
    ("MOD13Q1", "250m_16_days_VI_Quality", None),
    ("MOD16A2GF", "ET_500m", 0.1),
    ("MOD16A2GF", "ET_QC_500m", None),
]

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def get_json(url, params=None):
    for attempt in range(4):
        try:
            response = session.get(url, params=params, timeout=90)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def get_dates(product):
    data = get_json(f"{BASE}/{product}/dates", {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
    })

    if isinstance(data, dict):
        dates = data.get("dates", [])
    else:
        dates = data

    selected = [
        item for item in dates
        if START <= item.get("calendar_date", "") <= END
    ]

    selected.sort(key=lambda item: item["calendar_date"])
    return selected


def chunks(items, size=10):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def extract_band(product, band, scale, dates):
    records = []
    raw_batches = list(chunks(dates, 10))
    total = len(raw_batches)

    print(f"\n{product} | {band}")
    print(f"Dates: {len(dates)} | Requests: {total}")

    for batch_number, batch in enumerate(raw_batches, 1):
        allowed_dates = {item["modis_date"] for item in batch}

        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "band": band,
            "startDate": batch[0]["modis_date"],
            "endDate": batch[-1]["modis_date"],
            "kmAboveBelow": 1,
            "kmLeftRight": 1,
        }

        data = get_json(f"{BASE}/{product}/subset", params)
        subset = data.get("subset", [])

        for item in subset:
            if item.get("modis_date") not in allowed_dates:
                continue

            pixels = item.get("data", [])
            center_index = len(pixels) // 2
            raw_value = pixels[center_index] if pixels else None

            scaled_value = None
            if raw_value is not None and scale is not None:
                scaled_value = raw_value * scale

            records.append({
                "date": item.get("calendar_date"),
                "modis_date": item.get("modis_date"),
                "tile": item.get("tile", item.get("title")),
                "center_raw": raw_value,
                "center_scaled": scaled_value,
                "units": data.get("units"),
                "scale": data.get("scale", scale),
                "resolution_m": data.get("cellsize"),
                "rows": data.get("nrows"),
                "columns": data.get("ncols"),
                "pixel_count": len(pixels),
            })

        print(f"  Batch {batch_number}/{total}: "
              f"{len(records)} records collected")

        time.sleep(0.2)

    records.sort(key=lambda row: row["date"] or "")

    stem = f"{product}_{band}"

    csv_path = OUTPUT / f"{stem}.csv"
    if records:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)

    json_path = OUTPUT / f"{stem}.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

    print(f"Saved: {csv_path}")
    print(f"Records saved: {len(records)}")

    return len(records)


def main():
    date_cache = {}

    for product in ("MOD13Q1", "MOD16A2GF"):
        print(f"\nFetching available dates: {product}")
        date_cache[product] = get_dates(product)

        with (OUTPUT / f"{product}_available_dates.json").open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(date_cache[product], file, indent=2)

        print(f"Available dates in requested period: "
              f"{len(date_cache[product])}")

    summary = []

    for product, band, scale in PRODUCTS:
        count = extract_band(
            product, band, scale, date_cache[product]
        )
        summary.append({
            "product": product,
            "band": band,
            "records": count,
        })

    with (OUTPUT / "extraction_summary.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=2)

    print("\n========== EXTRACTION SUMMARY ==========")
    for item in summary:
        print(f"{item['product']} | {item['band']} | "
              f"{item['records']} records")

    print(f"\nOutput folder: {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
