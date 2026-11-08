"""Computer side: search the Steam store and look up each result's Steam Frame rating.

Uses the store's public endpoints (no key, no login):
  search/results                              full search, regional prices and pagination
  api/appdetails                               regional prices, game/DLC type and details
  app/<appid>/                                 labelled public review summaries
  saleaction/ajaxgetdeckappcompatibilityreport  per-app Deck/SteamOS/Machine/Frame ratings;
                                               `frame_resolved_category` is the Frame's
Buying happens on the store page, signed in as the user; nothing here buys.
"""
import http.client
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

STORE = "https://store.steampowered.com"
UA = {"User-Agent": "FrameControl/1 (+local)"}
COMPAT_TTL = 24 * 3600
DETAIL_TTL = 15 * 60
SEARCH_LIMIT = 50
SEARCH_TYPES = {"all": "", "game": "998", "dlc": "21"}
SEARCH_VR = {"all": "", "supported": "401,402", "required": "401"}
SEARCH_SORTS = {"relevance": "_ASC", "name": "Name_ASC", "price": "Price_ASC",
                "reviews": "Reviews_DESC", "released": "Released_DESC"}
SEARCH_PRICES = {"any": "", "free": "free", "10": "10", "25": "25", "50": "50"}
# IDs verified against Steam's public search tag controls (2026-11-05).
SEARCH_TAGS = {
    "21978": "VR", "4182": "Singleplayer", "3859": "Multiplayer", "1752": "Rhythm",
    "1774": "Shooter", "19": "Action", "492": "Indie", "1664": "Puzzle",
    "21": "Adventure", "1773": "Arcade", "1685": "Co-op", "3843": "Online Co-Op",
    "3841": "Local Co-Op", "7368": "Local Multiplayer", "599": "Simulation",
    "9": "Strategy", "122": "RPG", "597": "Casual", "699": "Racing", "701": "Sports",
    "1667": "Horror", "1663": "FPS", "1621": "Music", "1625": "Platformer",
    "1695": "Open World", "3810": "Sandbox", "1662": "Survival", "1742": "Story Rich",
    "3834": "Exploration", "1654": "Relaxing", "1716": "Roguelike", "3959": "Roguelite",
    "3839": "First-Person", "1697": "Third Person", "3942": "Sci-fi", "1684": "Fantasy",
    "1775": "PvP", "6730": "PvE", "493": "Early Access", "7481": "Controller",
}
SEARCH_TAG_LIMIT = 5


def valid_search_tags(tags):
    """A bounded, unique comma-separated intersection of known Steam tag IDs."""
    if not isinstance(tags, str) or len(tags) > 50:
        return False
    ids = tags.split(",") if tags else []
    return len(ids) <= SEARCH_TAG_LIMIT and len(ids) == len(set(ids)) and all(i in SEARCH_TAGS for i in ids)
# Editorial starting points, never presented as live rankings or recommendations.
VR_STARTERS = (620980, 546560, 418650, 611670, 400940, 438100)

_compat = {}  # appid -> (time, category)
_details = {}  # (appid, country) -> (time, public store data)
_lock = threading.Lock()


def _get(path, params, timeout=10):
    url = f"{STORE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def _get_text(path, params, timeout=5):
    url = f"{STORE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def frame_rating(appid, timeout=10):
    """0 unknown, 1 unsupported, 2 playable, 3 verified (same scale as the client's)."""
    with _lock:
        hit = _compat.get(appid)
    if hit and time.time() - hit[0] < COMPAT_TTL:
        return hit[1]
    try:
        r = _get("saleaction/ajaxgetdeckappcompatibilityreport", {"nAppID": appid, "l": "english"}, timeout=timeout)
        cat = int((r.get("results") or {}).get("frame_resolved_category") or 0)
        cat = cat if 0 <= cat <= 3 else 0
    except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
        return 0  # not cached, so the next search retries
    with _lock:
        _compat[appid] = (time.time(), cat)
    return cat


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "li", "p"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = _Text()
    parser.feed(str(value or ""))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


class SearchResults(HTMLParser):
    """Extract data, never forward Steam HTML, scripts or event attributes to the UI."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.row = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "search_result_row" in classes:
            match = re.match(r"https://store\.steampowered\.com/(app|sub|bundle)/(\d+)(?:/|$)", attrs.get("href", ""))
            if match:
                kind, appid = match.groups()
                self.row = {"id": int(appid) if kind == "app" else f"{kind}_{appid}",
                            "kind": kind, "name": "", "type": {"sub": "package", "bundle": "bundle"}.get(kind, "unknown"),
                            "price": None, "free": False, "frame": 0}
                self.stack = []
        if self.row is None:
            return
        if tag == "img" and not self.row.get("image"):
            self.row["image"] = attrs.get("src", "")
        if "search_review_summary" in classes:
            self.row["review_summary"] = "\n".join(plain_text(attrs.get("data-tooltip-html")).splitlines()[:2])
        if "discount_final_price" in classes and "free" in classes:
            self.row["free"] = True
        if tag not in ("img", "br", "hr", "input", "source", "wbr"):
            self.stack.append((tag, classes))

    def handle_data(self, data):
        if self.row is None:
            return
        classes = {c for _, names in self.stack for c in names}
        for cls, key in (("title", "name"), ("discount_final_price", "price_text"),
                         ("discount_original_price", "original_price_text"), ("discount_pct", "discount_text"), ("search_released", "release")):
            if cls in classes:
                self.row[key] = self.row.get(key, "") + data

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if tag == "a":
            for key in ("name", "price_text", "original_price_text", "release"):
                if key in self.row:
                    self.row[key] = self.row[key].strip()
            discount = re.fullmatch(r"-(\d{1,3})%", self.row.pop("discount_text", "").strip())
            if discount and 0 < int(discount[1]) <= 100:
                self.row["discount_percent"] = int(discount[1])
            if self.row["name"]:
                self.items.append(self.row)
            self.row = None
        else:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break


class ReviewSummaries(HTMLParser):
    """Read Steam's labelled public review summaries, preserving their language scope."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.capture = None
        self.tags = []
        self.tag_text = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "app_tag" in classes:
            self.tag_text = ""
        if tag == "a" and "user_reviews_summary_row" in classes and attrs.get("data-tooltip-html"):
            self.row = {"label": "", "rating": "", "description": plain_text(attrs["data-tooltip-html"])}
        if self.row is not None:
            if "subtitle" in classes:
                self.capture = (tag, "label")
            elif "game_review_summary" in classes:
                self.capture = (tag, "rating")

    def handle_data(self, data):
        if self.tag_text is not None:
            self.tag_text += data
        if self.row is not None and self.capture:
            self.row[self.capture[1]] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.tag_text is not None:
            value = self.tag_text.strip()
            if value and value not in self.tags and len(self.tags) < 10:
                self.tags.append(value)
            self.tag_text = None
        if self.capture and tag == self.capture[0]:
            self.capture = None
        if tag == "a" and self.row is not None:
            self.row = {k: v.strip() for k, v in self.row.items()}
            if self.row["label"] and self.row not in self.rows:
                self.rows.append(self.row)
            self.row = None
            self.capture = None


def search(term, cc, start=0, item_type="all", sort="relevance", vr="all", price="any", discount=False, tags="", hidef2p=False):
    """Public Steam result pages; type and sorting apply before pagination."""
    term = term.strip()[:100]
    if (item_type not in SEARCH_TYPES or sort not in SEARCH_SORTS or vr not in SEARCH_VR
            or price not in SEARCH_PRICES or not valid_search_tags(tags) or type(discount) is not bool
            or type(hidef2p) is not bool
            or type(start) is not int or not 0 <= start <= 1000000):
        raise ValueError("Invalid Steam search options")
    params = {"term": term, "cc": cc, "l": "english", "start": start, "count": SEARCH_LIMIT,
              "infinite": 1, "ignore_preferences": 1, "sort_by": SEARCH_SORTS[sort]}
    if SEARCH_TYPES[item_type]:
        params["category1"] = SEARCH_TYPES[item_type]
    if SEARCH_VR[vr]:
        params["vrsupport"] = SEARCH_VR[vr]
    if SEARCH_PRICES[price]:
        params["maxprice"] = SEARCH_PRICES[price]
    if discount:
        params["specials"] = 1
    if tags:
        params["tags"] = tags
    if hidef2p:
        params["hidef2p"] = 1
    payload = _get("search/results/", params)
    if payload.get("success") not in (True, 1) or not isinstance(payload.get("results_html"), str):
        raise ValueError("Steam returned an invalid search page")
    total = int(payload.get("total_count"))
    parser = SearchResults()
    parser.feed(payload["results_html"])
    if total < 0 or (total > start and not parser.items):
        raise ValueError("Steam's search page could not be read. Open Steam or try again.")
    def rate(item):
        if item["kind"] == "app":
            item["frame"] = frame_rating(item["id"], timeout=3)
            if item_type != "all":
                item["type"] = item_type
        return item
    # Search already has regional prices and reviews; don't fetch 50 appdetails.
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(rate, parser.items))
    return {"results": results, "total": total, "start": start, "page_size": SEARCH_LIMIT,
            "has_more": start + SEARCH_LIMIT < total}


def details(appid, cc):
    """Public metadata only. Missing price/type stays unknown; failures are retried."""
    key = (appid, cc)
    with _lock:
        hit = _details.get(key)
    if hit and time.time() - hit[0] < DETAIL_TTL:
        return dict(hit[1])
    payload = _get("api/appdetails", {"appids": appid, "cc": cc, "l": "english"})
    entry = payload.get(str(appid)) or {}
    if not entry.get("success") or not isinstance(entry.get("data"), dict):
        raise ValueError("Steam has no public details for this title in this region")
    data = entry["data"]
    result = {"id": appid, "name": data.get("name", ""), "type": data.get("type") or "unknown",
              "price": data.get("price_overview"), "free": data.get("is_free") is True,
              "image": data.get("header_image"), "description": data.get("short_description") or "",
              "about": plain_text(data.get("about_the_game") or data.get("detailed_description")),
              # Missing is unknown, not zero. Steam can repeat IDs in its DLC list.
              "dlc_count": len(set(data["dlc"])) if isinstance(data.get("dlc"), list) else None,
              "movies": [{"name": m.get("name") or "Steam trailer", "thumbnail": m.get("thumbnail"),
                          "sources": [{"url": url, "type": mime} for url, mime in (
                              ((m.get("mp4") or {}).get("480"), "video/mp4"),
                              ((m.get("webm") or {}).get("480"), "video/webm"),
                              (m.get("hls_h264"), "application/vnd.apple.mpegurl"))
                              if isinstance(url, str) and url.startswith("https://")]}
                         for m in (data.get("movies") or [])[:6] if isinstance(m, dict)],
              "developers": data.get("developers") or [], "publishers": data.get("publishers") or [],
              "genres": [g["description"] for g in data.get("genres", []) if g.get("description")],
              "release": (data.get("release_date") or {}).get("date") or "",
              "base_game": data.get("fullgame"),
              "screenshots": [s["path_full"] for s in (data.get("screenshots") or [])[:6] if s.get("path_full")],
              "metascore": (data.get("metacritic") or {}).get("score"),
              "categories": [c["description"] for c in data.get("categories", []) if c.get("description")],
              "requirements": {k: plain_text(v) for k, v in (data.get("pc_requirements") if isinstance(data.get("pc_requirements"), dict) else {}).items()
                               if k in ("minimum", "recommended") and v}}
    try:
        reviews = ReviewSummaries()
        reviews.feed(_get_text(f"app/{appid}/", {"cc": cc, "l": "english"}))
        result["review_summaries"] = reviews.rows
        result["tags"] = reviews.tags
    except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
        result["review_summaries"] = []
        result["tags"] = []
    if result["review_summaries"]:
        review = next((r for r in result["review_summaries"] if "English" in r["label"]), result["review_summaries"][0])
        result["review_summary"] = f'{review["rating"]}\n{review["label"]} {review["description"]}'
    with _lock:
        _details[key] = (time.time(), result)
    return dict(result)


def _result(item, cc):
    appid = int(item["id"])
    result = {"id": appid, "name": item.get("name", ""), "price": item.get("price"),
              "image": item.get("tiny_image"), "metascore": item.get("metascore") or None,
              "type": "unknown", "free": False}
    try:
        extra = details(appid, cc)
        # Search can provide a price even if appdetails omits it in this region.
        result.update({k: v for k, v in extra.items() if v is not None and v != ""})
    except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
        pass  # Keep the match usable with an explicitly unknown type and price.
    result["frame"] = frame_rating(appid)
    return result


def browse(cc):
    """A small, named VR selection with current regional data, not fabricated offers."""
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda appid: _result({"id": appid}, cc), VR_STARTERS))
    available = [r for r in results if r["name"]]  # Unavailable region entries aren't blank cards.
    if not available:
        raise ValueError("Steam's VR starting points are unavailable right now. Try searching for a title.")
    return available
