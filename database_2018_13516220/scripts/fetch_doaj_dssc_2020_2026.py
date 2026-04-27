#!/usr/bin/env python3
"""Fetch DOAJ article metadata for recent DSSC/green dye papers.

The DOAJ article search API is public for metadata search. If DOAJ_API_KEY is
present in the environment, this script sends it as an Authorization header,
but it never prints or writes the key.
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_QUERIES = [
    "dye sensitized solar cell",
    "dye-sensitized solar cell",
    "DSSC natural dye",
    "DSSC bio-based dye",
    "DSSC metal-free organic dye",
    "eco friendly dye sensitized solar cell",
    "green dye sensitized solar cell",
]


def doaj_get(query, page, page_size, api_key=None, timeout=40):
    base = "https://doaj.org/api/search/articles/"
    params = urlencode({"page": page, "pageSize": page_size})
    url = base + quote(query, safe=":") + "?" + params
    headers = {"User-Agent": "dssc-doaj-metadata-fetcher/1.0"}
    if api_key:
        headers["Authorization"] = api_key
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def identifiers(bibjson):
    out = {}
    for item in bibjson.get("identifier", []) or []:
        kind = (item.get("type") or "").lower()
        value = item.get("id") or ""
        if kind and value:
            out[kind] = value
    return out


def links(bibjson):
    fulltext = []
    pdf = []
    for item in bibjson.get("link", []) or []:
        url = item.get("url") or ""
        kind = (item.get("type") or "").lower()
        if not url:
            continue
        if "pdf" in kind or url.lower().endswith(".pdf"):
            pdf.append(url)
        else:
            fulltext.append(url)
    return fulltext, pdf


def first_author(bibjson):
    authors = bibjson.get("author", []) or []
    if not authors:
        return ""
    return authors[0].get("name") or ""


def normalize_record(result, query):
    bibjson = result.get("bibjson", {}) or {}
    ids = identifiers(bibjson)
    fulltext, pdf = links(bibjson)
    journal = bibjson.get("journal", {}) or {}
    year = bibjson.get("year")
    return {
        "query": query,
        "doaj_id": result.get("id", ""),
        "year": year if year is not None else "",
        "title": bibjson.get("title", ""),
        "doi": ids.get("doi", ""),
        "issn": ids.get("pissn", "") or ids.get("issn", ""),
        "eissn": ids.get("eissn", ""),
        "journal": journal.get("title", ""),
        "publisher": journal.get("publisher", ""),
        "first_author": first_author(bibjson),
        "abstract": bibjson.get("abstract", ""),
        "keywords": "; ".join(bibjson.get("keywords", []) or []),
        "fulltext_url": "; ".join(fulltext),
        "pdf_url": "; ".join(pdf),
    }


def record_key(row):
    return (row.get("doi") or row.get("fulltext_url") or row.get("doaj_id") or row.get("title")).lower()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="database_2018_13516220/doaj_2020_2026")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.4)
    parser.add_argument("--query", action="append", dest="queries")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "doaj_dssc_articles_2020_2026.csv"
    jsonl_path = out_dir / "doaj_dssc_articles_2020_2026.jsonl"

    api_key = os.environ.get("DOAJ_API_KEY")
    queries = args.queries or DEFAULT_QUERIES
    rows_by_key = {}
    raw_results = []

    for query in queries:
        for page in range(1, args.max_pages + 1):
            try:
                payload = doaj_get(query, page, args.page_size, api_key=api_key)
            except Exception as exc:
                print(f"warning=query_failed query={query!r} page={page} error={exc.__class__.__name__}")
                break
            results = payload.get("results", []) or []
            if not results:
                break
            for result in results:
                row = normalize_record(result, query)
                try:
                    year = int(row["year"])
                except (TypeError, ValueError):
                    continue
                if args.start_year <= year <= args.end_year:
                    rows_by_key.setdefault(record_key(row), row)
                    raw_results.append(result)
            if len(results) < args.page_size:
                break
            time.sleep(args.sleep)

    rows = sorted(rows_by_key.values(), key=lambda r: (str(r["year"]), r["title"]), reverse=True)

    fieldnames = [
        "query",
        "year",
        "title",
        "doi",
        "journal",
        "publisher",
        "first_author",
        "issn",
        "eissn",
        "keywords",
        "fulltext_url",
        "pdf_url",
        "abstract",
        "doaj_id",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"csv={csv_path}")
    print(f"jsonl={jsonl_path}")
    print(f"records={len(rows)}")
    print(f"api_key_present={'yes' if bool(api_key) else 'no'}")


if __name__ == "__main__":
    main()
