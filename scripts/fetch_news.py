# -*- coding: utf-8 -*-
"""
Скачивает RSS Google News для заданной темы, берёт последние 5,
формирует краткий JSON (title, snippet, source, url, published_at)
и записывает в data/news.json, если список новостей изменился.
"""
import os, re, json, time, datetime as dt
from urllib.parse import urlparse, parse_qs, unquote
import xml.etree.ElementTree as ET
import urllib.request, urllib.error

TOPIC_RSS = "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNREprZG5Sa0VnSnlkU2dBUAE?hl=ru&gl=RU&ceid=RU:ru"
OUT_PATH = os.path.join("data", "news.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def strip_tags(html):
    # Небольшая чистка description от HTML
    return re.sub(r"<[^>]+>", "", html or "").strip()

def resolve_publisher_url(gn_url):
    """
    Иногда ссылки из Google News ведут на news.google.com/articles/...
    Попробуем вытащить прямую ссылку, если в query есть 'url=',
    иначе последуем редиректу.
    """
    try:
        q = urlparse(gn_url).query
        if q:
            qs = parse_qs(q)
            if "url" in qs and qs["url"]:
                return unquote(qs["url"][0])
        # Fallback: одно обращение с редиректом
        req = urllib.request.Request(gn_url, headers={"User-Agent": UA})
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        with opener.open(req, timeout=20) as r:
            return r.geturl()
    except Exception:
        pass
    return gn_url

def parse_rss(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        src_el = item.find("{http://www.w3.org/2005/Atom}source")
        source = (src_el.text or "").strip() if src_el is not None else (item.findtext("source") or "").strip()
        pub_raw = item.findtext("pubDate") or ""
        try:
            # RFC822 -> ISO 8601
            pub_ts = time.mktime(time.strptime(pub_raw[:25], "%a, %d %b %Y %H:%M:%S"))
            published = dt.datetime.utcfromtimestamp(pub_ts).replace(microsecond=0).isoformat() + "Z"
        except Exception:
            published = ""

        items.append({
            "title": title,
            "snippet": strip_tags(desc)[:220],
            "source": source,
            "url": resolve_publisher_url(link),
            "published_at": published
        })
    return items

def load_existing():
    if not os.path.exists(OUT_PATH):
        return {"items": []}
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": []}

def main():
    xml = fetch(TOPIC_RSS)
    items = parse_rss(xml)[:5]
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    data_old = load_existing()
    # Сравниваем только список новостей (без generated_at), чтобы не коммитить зря
    old_key = [(i.get("title"), i.get("url"), i.get("published_at")) for i in data_old.get("items", [])]
    new_key = [(i.get("title"), i.get("url"), i.get("published_at")) for i in items]

    if old_key == new_key:
        print("No changes in items; skipping write.")
        return 0

    out = {
        "topic_url": TOPIC_RSS.replace("/rss/", "/"),  # на всякий случай
        "generated_at": now,
        "items": items
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Wrote", OUT_PATH)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
