#!/usr/bin/env python
"""Download and extract the OULAD dataset (Phase 1).

The official Open University download endpoint is currently broken (the
analyse.kmi.open.ac.uk URLs redirect to a landing page and the STEM CDN link
returns 404). This script therefore tries the official URL first and falls
back to a verified GitHub mirror containing the identical anonymisedData.zip
(all 7 CSVs match the published row counts).

Extracts the CSV tables into data/oulad/raw/. The schema mapping into
CAREERMIND collections is documented in data/oulad/README.md.
"""
import argparse
import pathlib
import sys
import urllib.request
import zipfile

OULAD_URLS = [
    # Official (currently redirects to landing page / 404, kept first in case it returns)
    "https://schools.stem.open.ac.uk/cdn/files/anonymisedData.zip",
    "https://analyse.kmi.open.ac.uk/open_dataset/download",
    # Verified mirror: all 7 tables match published row counts
    "https://raw.githubusercontent.com/Timothy-Dement/OULAD/master/data.zip",
]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

EXPECTED_ROW_COUNTS = {  # data rows (excluding header), per Kuzilek et al. 2017
    "courses.csv": 22,
    "assessments.csv": 206,
    "vle.csv": 6364,
    "studentInfo.csv": 32593,
    "studentRegistration.csv": 32593,
    "studentAssessment.csv": 173912,
    "studentVle.csv": 10655280,
}


def fetch(url: str, dest: pathlib.Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as response, open(dest, "wb") as fh:
            fh.write(response.read())
        return zipfile.is_zipfile(dest)
    except Exception as exc:  # noqa: BLE001 - report and try the next mirror
        print(f"  failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OULAD")
    parser.add_argument("--out", default="data/oulad/raw/", help="Output directory")
    parser.add_argument("--skip-check", action="store_true", help="Skip row-count validation")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "oulad.zip"

    if not zip_path.exists():
        for url in OULAD_URLS:
            print(f"Trying {url} ...")
            if fetch(url, zip_path):
                print(f"Downloaded from {url}")
                break
            zip_path.unlink(missing_ok=True)
        else:
            print("All download sources failed.")
            return 1
    else:
        print(f"Using existing {zip_path}")

    print(f"Extracting to {out_dir} ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)

    csvs = sorted(out_dir.glob("*.csv"))
    print(f"Done. {len(csvs)} CSV tables available: {[c.name for c in csvs]}")

    if not args.skip_check:
        for name, expected in EXPECTED_ROW_COUNTS.items():
            path = out_dir / name
            if not path.exists():
                print(f"  WARNING: {name} missing")
                continue
            with open(path) as fh:
                n = sum(1 for _ in fh) - 1
            status = "OK" if n == expected else f"WARNING: expected {expected}"
            print(f"  {name}: {n} rows {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
