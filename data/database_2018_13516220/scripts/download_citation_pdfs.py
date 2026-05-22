#!/usr/bin/env python3
"""Download PDFs advertised in scraped HTML metadata."""

import re
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


RAW_DIR = Path("database_2018_13516220/doaj_2020_2026/scraped/raw")


def clean_url(url):
    url = (url or "").strip()
    if url.startswith("[") and url.endswith("]"):
        url = url[1:-1]
    return url


def safe_pdf_name(html_path):
    return html_path.with_suffix(".pdf")


def main():
    downloaded = 0
    skipped = 0
    failed = 0
    for html_path in RAW_DIR.glob("*.html"):
        pdf_path = safe_pdf_name(html_path)
        if pdf_path.exists():
            skipped += 1
            continue
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if not meta or not meta.get("content"):
            skipped += 1
            continue
        url = clean_url(meta["content"])
        try:
            req = Request(url, headers={"User-Agent": "dssc-pdf-fetcher/1.0"})
            with urlopen(req, timeout=60) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                failed += 1
                continue
            pdf_path.write_bytes(data)
            downloaded += 1
        except Exception:
            failed += 1
    print(f"downloaded={downloaded}")
    print(f"skipped={skipped}")
    print(f"failed={failed}")


if __name__ == "__main__":
    main()
