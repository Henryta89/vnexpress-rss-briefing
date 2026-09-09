from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


FEEDS = [
    {
        "name": "Khoa học công nghệ",
        "url": "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss",
        "limit": 3,
    },
    {
        "name": "Sức khỏe",
        "url": "https://vnexpress.net/rss/suc-khoe.rss",
        "limit": 3,
    },
    {
        "name": "Tin xem nhiều",
        "url": "https://vnexpress.net/rss/tin-xem-nhieu.rss",
        "limit": 10,
    },
]

OUTPUT = Path("docs/index.html")
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; VnExpress-RSS-Briefing/1.0)"
            )
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(
                f"HTTP {response.status} while fetching {url}"
            )

        return response.read()


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<img[^>]*>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def child_text(item: ET.Element, name: str) -> str:
    child = item.find(name)

    if child is None or child.text is None:
        return ""

    return child.text.strip()


def read_feed(feed: dict) -> list[dict]:
    xml_data = fetch_url(feed["url"])

    root = ET.fromstring(xml_data)
    channel = root.find("channel")

    if channel is None:
        raise RuntimeError(
            f"RSS channel not found: {feed['name']}"
        )

    rss_items = channel.findall("item")

    if len(rss_items) < feed["limit"]:
        raise RuntimeError(
            f"{feed['name']} returned only "
            f"{len(rss_items)} items; "
            f"{feed['limit']} required"
        )

    result = []

    for rank, item in enumerate(
        rss_items[: feed["limit"]],
        start=1,
    ):
        result.append(
            {
                "rank": rank,
                "title": clean_text(
                    child_text(item, "title")
                ),
                "link": child_text(item, "link"),
                "pub_date": clean_text(
                    child_text(item, "pubDate")
                ),
                "description": clean_text(
                    child_text(item, "description")
                ),
            }
        )

    return result


def escape(value: object) -> str:
    return html.escape(
        str(value),
        quote=True,
    )


def build_html(feeds: list[dict]) -> str:
    now = datetime.now(TIMEZONE)

    generated = now.strftime(
        "%Y-%m-%d %H:%M:%S Asia/Ho_Chi_Minh"
    )

    parts = [
        "<!DOCTYPE html>",
        '<html lang="vi">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" '
        'content="width=device-width, initial-scale=1.0">',
        '<meta name="robots" content="noindex,nofollow">',
        "<title>VnExpress RSS Briefing Source</title>",
        """
<style>
body {
    font-family: Arial, sans-serif;
    max-width: 960px;
    margin: 30px auto;
    padding: 0 20px;
    line-height: 1.6;
}
h1 {
    margin-bottom: 4px;
}
h2 {
    margin-top: 38px;
    padding-bottom: 6px;
    border-bottom: 1px solid #ddd;
}
article {
    margin: 24px 0;
}
.metadata {
    font-size: 0.9em;
}
.description {
    margin: 8px 0;
}
a {
    word-break: break-all;
}
</style>
""",
        "</head>",
        "<body>",
        "<h1>VnExpress RSS Briefing Source</h1>",
        (
            "<p><strong>Updated:</strong> "
            f"{escape(generated)}</p>"
        ),
        (
            "<p><strong>Source authority:</strong> "
            "VnExpress RSS</p>"
        ),
    ]

    for feed in feeds:
        parts.append(
            f"<section><h2>{escape(feed['name'])}</h2>"
        )

        parts.append(
            "<p>"
            f"<strong>Status:</strong> OK &nbsp; | &nbsp; "
            f"<strong>Returned:</strong> "
            f"{len(feed['items'])}"
            "</p>"
        )

        for item in feed["items"]:
            parts.extend(
                [
                    "<article>",
                    (
                        "<h3>"
                        f"{item['rank']}. "
                        f"{escape(item['title'])}"
                        "</h3>"
                    ),
                    (
                        '<p class="metadata">'
                        "<strong>Publication time:</strong> "
                        f"{escape(item['pub_date'] or 'Not available')}"
                        "</p>"
                    ),
                    (
                        '<p class="description">'
                        f"{escape(item['description'])}"
                        "</p>"
                    ),
                    (
                        "<p><strong>Article:</strong> "
                        f'<a href="{escape(item["link"])}">'
                        f"{escape(item['link'])}"
                        "</a></p>"
                    ),
                    "</article>",
                    "<hr>",
                ]
            )

        parts.append("</section>")

    parts.extend(
        [
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(parts)


def main() -> None:
    completed_feeds = []

    # Important:
    # If ANY feed fails, the script exits before replacing
    # the last known-good published page.
    for feed in FEEDS:
        print(f"Fetching: {feed['name']}")

        items = read_feed(feed)

        print(
            f"  OK: {len(items)} / "
            f"{feed['limit']} items"
        )

        completed_feeds.append(
            {
                **feed,
                "items": items,
            }
        )

    page = build_html(completed_feeds)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_output = OUTPUT.with_suffix(".tmp")
    temp_output.write_text(
        page,
        encoding="utf-8",
    )

    temp_output.replace(OUTPUT)

    print(f"Published: {OUTPUT}")


if __name__ == "__main__":
    main()
