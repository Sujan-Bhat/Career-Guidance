#!/usr/bin/env python
"""Download and extract the OULAD dataset (Phase 1).

Fetches the dataset zip from the Open University Learning Analytics site and
extracts the CSV tables into data/oulad/raw/. The schema mapping into
CAREERMIND collections is documented in data/oulad/README.md.
"""
import argparse
import pathlib
import sys
import urllib.request
import zipfile

OULAD_URL = "https://analyse.kmi.open.ac.uk/open_dataset/download"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OULAD")
    parser.add_argument("--out", default="data/oulad/raw/", help="Output directory")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "oulad.zip"

    if not zip_path.exists():
        print(f"Downloading OULAD from {OULAD_URL} ...")
        urllib.request.urlretrieve(OULAD_URL, zip_path)

    print(f"Extracting to {out_dir} ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)

    csvs = sorted(out_dir.glob("*.csv"))
    print(f"Done. {len(csvs)} CSV tables available: {[c.name for c in csvs]}")
    print("Phase 1 will map these into CAREERMIND MongoDB collections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
