#!/usr/bin/env python3
"""
Image search for article illustrations.

Search Pexels (primary) and Pixabay (fallback), download top match.

Usage:
  python3 image_search.py "<query>" <output_dir> [--index N]
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


# ── Config ──
PEXELS_API_KEY = "IupPtrTI2BG3nKYHvuSBDpZmL4bX48FvCY3HxV4BiN1BvgtQhRJM1to3"
PEXELS_URL = "https://api.pexels.com/v1/search"
PIXABAY_API_KEY = "46539967-a28550dda0098c01b6a752b00"
PIXABAY_URL = "https://pixabay.com/api/"

# Allowed image types
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Maximum image file size (5 MB)
MAX_FILE_SIZE = 5 * 1024 * 1024


def search_pexels(query: str, per_page: int = 5) -> list[dict]:
    """Search Pexels and return list of photo dicts."""
    params = urllib.parse.urlencode({"query": query, "per_page": per_page, "orientation": "landscape"})
    url = f"{PEXELS_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("photos", [])
    except Exception as e:
        print(f"    ⚠️ Pexels search failed: {e}")
        return []


def search_pixabay(query: str, per_page: int = 5) -> list[dict]:
    """Search Pixabay and return list of image dicts."""
    params = urllib.parse.urlencode({
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": per_page,
        "image_type": "photo",
        "orientation": "horizontal",
        "safesearch": "true",
    })
    url = f"{PIXABAY_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("hits", [])
    except Exception as e:
        print(f"    ⚠️ Pixabay search failed: {e}")
        return []


def download_image(url: str, output_path: Path) -> bool:
    """Download image from URL to output_path. Returns success."""
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    # Enforce extension
    final_path = output_path.with_suffix(ext)

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()

            # Check file size
            if len(data) > MAX_FILE_SIZE:
                print(f"    ⚠️ Image too large ({len(data) / 1024 / 1024:.1f} MB), skipping")
                return False

            # Check content type
            if "image" not in content_type:
                print(f"    ⚠️ Not an image (Content-Type: {content_type}), skipping")
                return False

            # Infer extension from content type if not already set
            if ext == ".jpg" and "png" in content_type:
                final_path = final_path.with_suffix(".png")

            final_path.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"    ✓ Downloaded: {final_path.name} ({size_kb:.0f} KB)")
            return True

    except Exception as e:
        print(f"    ⚠️ Download failed: {e}")
        return False


def search(query: str) -> list[dict]:
    """Search Pexels first, fall back to Pixabay."""
    results = search_pexels(query)
    if results:
        return results

    # Fallback to Pixabay
    pixabay_results = search_pixabay(query)
    if pixabay_results:
        return pixabay_results

    return []


def main():
    parser = argparse.ArgumentParser(description="Search and download images for articles")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("output_dir", type=str, help="Output directory for downloaded images")
    parser.add_argument("--index", type=int, default=1, help="Image index in the article (1-based)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Search
    photos = search(args.query)

    if not photos:
        print(f"  ❌ No images found for: {args.query}")
        sys.exit(1)

    # Try to download the best one
    for photo in photos:
        # Pexels format
        url = None
        if "src" in photo:
            # Try medium then original
            url = photo["src"].get("medium") or photo["src"].get("original")
            # Prefer landscape for article headers
            if photo["src"].get("landscape"):
                url = photo["src"]["landscape"]
        # Pixabay format
        elif "webformatURL" in photo:
            url = photo.get("webformatURL") or photo.get("largeImageURL")

        if not url:
            continue

        # Remove query params for clean name
        clean_query = args.query.replace(" ", "-").lower()[:30]
        output_path = output_dir / f"image-{args.index:03d}-pexels"
        if download_image(url, output_path):
            # Create metadata json
            meta_path = output_dir / "metadata.json"
            meta = {}
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
            meta[str(args.index)] = {
                "query": args.query,
                "source": "pexels" if "src" in photo else "pixabay",
                "url": url,
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            sys.exit(0)

    print(f"  ❌ Failed to download any image for: {args.query}")
    sys.exit(1)


if __name__ == "__main__":
    main()
