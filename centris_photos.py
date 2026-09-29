#!/usr/bin/env python3
"""Download all photos from a Centris listing.

Usage: python3 centris_photos.py <centris-url> [output-folder]
"""
import os
import re
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
PHOTO_URL = "https://mspublic.centris.ca/media.ashx?id={}&t=pi&w=1260&h=1024&sm=m"


def fetch(url):
    return subprocess.run(["curl", "-sfL", "--max-time", "60", "-A", UA, url],
                          capture_output=True, check=True).stdout


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 centris_photos.py <centris-url> [output-folder]")
    url = sys.argv[1]
    listing_id = re.search(r"/(\d+)(?:[/?#]|$)", url)
    out = sys.argv[2] if len(sys.argv) > 2 else f"centris_{listing_id.group(1) if listing_id else 'photos'}"

    html = fetch(url).decode("utf-8", "replace")
    # The gallery list (MosaicPhotoUrls) holds every photo, in order
    block = re.search(r"MosaicPhotoUrls\s*=\s*\[(.*?)\]", html, re.S)
    ids = re.findall(r"media\.ashx\?id=([0-9A-F]+)", block.group(1) if block else html)
    ids = list(dict.fromkeys(ids))  # dedupe, keep order
    if not ids:
        sys.exit("No photos found (the page layout may have changed or the request was blocked).")

    os.makedirs(out, exist_ok=True)
    print(f"Found {len(ids)} photos -> {out}/")

    def download(item):
        n, pid = item
        path = os.path.join(out, f"{n:02d}.jpg")
        with open(path, "wb") as f:
            f.write(fetch(PHOTO_URL.format(pid)))
        return path

    with ThreadPoolExecutor(8) as pool:
        for path in pool.map(download, enumerate(ids, 1)):
            print(f"  saved {path}")
    print("Done.")


if __name__ == "__main__":
    main()
