"""Parser layer for Jimoty search results (SSR HTML) and detail pages (__NEXT_DATA__ JSON + HTML fallback)."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from jimoty.config import BASE_URL
from jimoty.models import (
    ListingDetail,
    ListingSummary,
    Location,
    SellerProfile,
)

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Raised when parsing fails on unexpected markup or malformed payload."""


# ---------------------------------------------------------------------------
# Utility Normalizers & Cleaners
# ---------------------------------------------------------------------------


def clean_text(text: Optional[str]) -> str:
    """Normalize Japanese Unicode characters and whitespace using NFKC."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    # Replace full-width space and multiple spaces with a single space
    cleaned = re.sub(r"[\s\u3000\xa0]+", " ", normalized).strip()
    return cleaned


def extract_price(raw_val: Any) -> Tuple[int, str, bool]:
    """
    Parse price into (int_price, price_text, is_free).
    Handles:
      - 0, "0", "0円", "無料" -> (0, "0円" or "無料", True)
      - 50000, "50,000円", "50000", "¥50,000" -> (50000, "50,000円", False)
      - "要相談", "応相談", None -> (0, raw_str, False)
    """
    if raw_val is None:
        return 0, "0円", True

    if isinstance(raw_val, (int, float)):
        int_price = int(raw_val)
        return int_price, f"{int_price:,}円", (int_price == 0)

    raw_str = clean_text(str(raw_val))
    if not raw_str:
        return 0, "0円", True

    # Check for free
    if "無料" in raw_str or raw_str in ("0円", "0", "¥0", "￥0"):
        return 0, raw_str, True

    # Extract digits with optional commas
    digit_match = re.search(r"([0-9,]+)", raw_str)
    if digit_match:
        digits = digit_match.group(1).replace(",", "")
        if digits.isdigit():
            val = int(digits)
            return val, raw_str, (val == 0)

    # Could not extract numeric price
    return 0, raw_str, False


def parse_datetime(val: Any) -> Optional[datetime]:
    """Attempt to parse ISO date string or timestamp into a datetime object."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        try:
            # Check if timestamp in milliseconds
            ts = float(val)
            if ts > 1e11:
                ts /= 1000.0
            return datetime.fromtimestamp(ts)
        except Exception:
            return None

    date_str = str(val).strip()
    try:
        # Standard ISO 8601
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        pass

    # Try common formats e.g. "2026-09-30 15:30:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue

    return None


def parse_location_hierarchy(raw_loc: str) -> Location:
    """Parse hierarchical location text into Location model."""
    cleaned = clean_text(raw_loc)
    loc = Location(raw_text=cleaned)
    if not cleaned:
        return loc

    # Often separated by slashes, commas, dashes, or spaces (e.g. "神奈川 - 茅ヶ崎市 - 茅ヶ崎駅")
    delimiters = r"[\/,、\-\s]+"
    parts = [p.strip() for p in re.split(delimiters, cleaned) if p.strip()]

    for part in parts:
        if part.endswith(("県", "都", "府", "道")) or part in ("神奈川", "東京", "埼玉", "千葉"):
            loc.prefecture = part
        elif part.endswith(("市", "区", "町", "村")):
            loc.city = part
        elif part.endswith("駅"):
            loc.station = part
        elif not loc.town and loc.city:
            loc.town = part

    return loc


# ---------------------------------------------------------------------------
# Search Page Parser (SSR HTML)
# ---------------------------------------------------------------------------


def parse_search_page(html: str, base_url: str = BASE_URL) -> List[ListingSummary]:
    """
    Parse SSR HTML search results page and extract structured ListingSummary items.
    Parses listing cards with exact class `p-articles-list-item` or containing `data-article-id`.
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: List[ListingSummary] = []

    # Find distinct article item elements (avoid matching child elements like p-articles-list-item__title)
    items = soup.find_all(
        lambda tag: tag.name in ("div", "li", "article")
        and (
            (tag.has_attr("class") and any(c in ("p-articles-list-item", "articles-list-item", "c-article-item") for c in tag["class"]))
            or (tag.has_attr("data-article-id") and tag.select_one("a[href*='/article']"))
        )
    )

    if not items:
        # Fallback to top-level cards containing article links and price
        candidates = soup.select("li, div.article-card, article")
        seen_parents = set()
        for cand in candidates:
            if cand.select_one("a[href*='/article']") and cand.select_one("[class*='price']"):
                # Ensure not already a child of another candidate
                parent_cand = cand.find_parent(lambda p: p in candidates)
                if not parent_cand:
                    items.append(cand)

    seen_ids = set()
    for item in items:
        summary = _parse_search_item(item, base_url)
        if summary:
            # Deduplicate by item id if present
            if summary.id and summary.id in seen_ids:
                continue
            if summary.id:
                seen_ids.add(summary.id)
            listings.append(summary)

    return listings


def _parse_search_item(item: Tag, base_url: str) -> Optional[ListingSummary]:
    """Extract ListingSummary from a single search item HTML node."""
    # 1. Title & URL
    title_el = item.select_one(".p-articles-list-item__title a, [class*='title'] a, a.p-articles-list-item__title")
    link_el = title_el or item.select_one("a[href*='/article'], a")
    if not link_el or not link_el.get("href"):
        return None

    href = link_el["href"]
    full_url = urljoin(base_url, href)

    title = ""
    if title_el:
        title = clean_text(title_el.get_text())
    if not title and link_el:
        title = clean_text(link_el.get_text())
    if not title:
        img_el = item.select_one("img[alt]")
        if img_el and img_el.get("alt"):
            title = clean_text(img_el["alt"])

    # 2. Extract item ID
    item_id = item.get("data-article-id") or item.get("data-id") or ""
    if not item_id:
        id_match = re.search(r"article[s]?-([a-zA-Z0-9]+)", href)
        if id_match:
            item_id = id_match.group(1)
        else:
            item_id = href.rstrip("/").split("/")[-1]

    # 3. Price
    price_el = item.select_one(".p-item-most-important, .p-articles-list-item__price, [class*='price']")
    raw_price_str = clean_text(price_el.get_text()) if price_el else ""
    price_val, price_text, is_free = extract_price(raw_price_str)

    # 4. Thumbnail Image
    img_el = item.select_one("img")
    thumbnail_url: Optional[str] = None
    if img_el:
        src = (
            img_el.get("src")
            or img_el.get("data-src")
            or img_el.get("data-original")
            or img_el.get("data-lazy")
        )
        if src and not src.startswith("data:image"):
            thumbnail_url = urljoin(base_url, src)

    # 5. Location
    loc_el = item.select_one(".p-item-supplementary-info, .p-articles-list-item__location, [class*='location'], [class*='place']")
    loc_text = clean_text(" ".join(loc_el.get_text().split())) if loc_el else None
    location = parse_location_hierarchy(loc_text) if loc_text else None

    # 6. Date / Timestamp
    date_el = item.select_one(".p-item-history, .p-item-additional-info, .p-articles-list-item__date, time, [class*='date'], [class*='time']")
    date_text = clean_text(" ".join(date_el.get_text().split())) if date_el else None
    created_at = None
    if date_el and date_el.get("datetime"):
        created_at = parse_datetime(date_el["datetime"])
    if not created_at and date_text:
        created_at = parse_datetime(date_text)

    # 7. Category name
    cat_el = item.select_one(".p-articles-list-item__category, [class*='category']")
    category_name = clean_text(cat_el.get_text()) if cat_el else None

    return ListingSummary(
        id=str(item_id),
        title=title,
        url=full_url,
        price=price_val,
        price_text=price_text,
        thumbnail_url=thumbnail_url,
        location=location,
        location_text=loc_text,
        created_at=created_at,
        created_at_text=date_text,
        is_free=is_free,
        category_name=category_name,
    )


# ---------------------------------------------------------------------------
# Detail Page Parser (__NEXT_DATA__ JSON + Fallback)
# ---------------------------------------------------------------------------


def parse_detail_page(html: str, base_url: str = BASE_URL) -> ListingDetail:
    """
    Extract structured listing detail from a Jimoty detail page.
    Attempts extraction from embedded `<script id="__NEXT_DATA__">` JSON first.
    Falls back to BeautifulSoup HTML extraction if __NEXT_DATA__ is absent or incomplete.
    """
    if not html or not html.strip():
        raise ParserError("Empty HTML provided to parse_detail_page")

    soup = BeautifulSoup(html, "html.parser")

    # 1. Attempt Next.js __NEXT_DATA__ extraction
    next_data_script = soup.select_one("script#__NEXT_DATA__")
    if next_data_script and next_data_script.string:
        try:
            data = json.loads(next_data_script.string.strip())
            detail = _parse_detail_from_next_data(data, soup, html, base_url)
            if detail:
                return detail
        except json.JSONDecodeError as e:
            logger.warning("Failed to decode __NEXT_DATA__ JSON: %s. Using HTML fallback.", e)
        except Exception as e:
            logger.warning("Error parsing __NEXT_DATA__ data: %s. Using HTML fallback.", e)

    # 2. Check if the input itself might be raw JSON (useful for direct testing)
    trimmed = html.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            data = json.loads(trimmed)
            detail = _parse_detail_from_next_data(data, soup, html, base_url)
            if detail:
                return detail
        except Exception:
            pass

    # 3. BeautifulSoup HTML fallback
    return _parse_detail_from_html(soup, html, base_url)


def _locate_article_and_user(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Locate article and post_user across various Next.js schema representations."""
    if not isinstance(data, dict):
        return None, None

    # Check top-level 'article'
    if "article" in data and isinstance(data["article"], dict):
        article = data["article"]
        user = article.get("post_user") or data.get("post_user") or data.get("user")
        return article, user

    # Check props.pageProps
    page_props = data.get("props", {}).get("pageProps", {}) if "props" in data else data.get("pageProps", {})
    if isinstance(page_props, dict):
        # 1. articleResults.article & articleResults.post_user
        results = page_props.get("articleResults")
        if isinstance(results, dict):
            article = results.get("article")
            user = results.get("post_user") or (article.get("post_user") if isinstance(article, dict) else None)
            if article and isinstance(article, dict):
                return article, user

        # 2. pageProps.article
        if "article" in page_props and isinstance(page_props["article"], dict):
            article = page_props["article"]
            user = article.get("post_user") or page_props.get("post_user") or page_props.get("user")
            return article, user

        # 3. pageProps.articleDetail
        if "articleDetail" in page_props and isinstance(page_props["articleDetail"], dict):
            article = page_props["articleDetail"]
            user = article.get("post_user") or page_props.get("post_user") or page_props.get("user")
            return article, user

    # Recursively check top-level dict for first key that contains 'article'
    for k, v in data.items():
        if isinstance(v, dict) and "article" in v and isinstance(v["article"], dict):
            return v["article"], v.get("post_user") or v["article"].get("post_user")

    return None, None


def _parse_detail_from_next_data(
    data: Dict[str, Any],
    soup: BeautifulSoup,
    raw_html: str,
    base_url: str,
) -> Optional[ListingDetail]:
    """Parse article and post_user from Next.js pageProps data."""
    article, post_user = _locate_article_and_user(data)
    if not article or not isinstance(article, dict):
        return None

    # 1. ID & Title
    item_id = str(article.get("id") or article.get("article_id") or "")
    title = clean_text(article.get("title") or "")
    if not title:
        og_title = soup.select_one("meta[property='og:title']")
        if og_title and og_title.get("content"):
            title = clean_text(og_title["content"])

    # 2. URL
    url = article.get("url") or article.get("canonical_url")
    if url:
        full_url = urljoin(base_url, url)
    else:
        og_url = soup.select_one("meta[property='og:url']")
        if og_url and og_url.get("content"):
            full_url = og_url["content"]
        else:
            full_url = urljoin(base_url, f"/articles/{item_id}")

    # 3. Price
    par_cat = article.get("par_category_items") or {}
    raw_price = par_cat.get("price") if isinstance(par_cat, dict) else None
    if raw_price is None:
        raw_price = article.get("price")

    raw_price_str = (
        article.get("important_field")
        or article.get("price_formatted")
        or article.get("price_str")
        or article.get("price_text")
    )
    if raw_price_str:
        price_val, price_text, is_free = extract_price(raw_price_str)
    elif raw_price is not None:
        price_val, price_text, is_free = extract_price(raw_price)
    else:
        price_el = soup.select_one(".p-item-most-important, [class*='price'], [itemprop='price']")
        if price_el:
            price_val, price_text, is_free = extract_price(price_el.get_text())
        else:
            price_val, price_text, is_free = 0, "0円", True

    if article.get("is_free") is True or price_val == 0:
        is_free = True

    # 4. Description
    description = (
        article.get("description")
        or article.get("body")
        or article.get("text")
        or article.get("content")
        or ""
    )
    description = clean_text(description)
    if not description:
        desc_el = soup.select_one(
            ".p-article-detail__body, .p-article-description, .p-article__content, [itemprop='description']"
        )
        if desc_el:
            description = clean_text(desc_el.get_text())

    # 5. Image URLs
    image_urls: List[str] = []
    raw_images = article.get("images") or article.get("image_urls") or article.get("photos") or []
    if isinstance(raw_images, list):
        for img in raw_images:
            if isinstance(img, str) and img.strip():
                image_urls.append(urljoin(base_url, img.strip()))
            elif isinstance(img, dict):
                src = img.get("url") or img.get("original") or img.get("large") or img.get("src")
                if src and isinstance(src, str):
                    image_urls.append(urljoin(base_url, src.strip()))

    if not image_urls:
        for img_tag in soup.select(".p-article-detail__images img, .p-article-images img, .image-gallery img"):
            src = img_tag.get("src") or img_tag.get("data-src")
            if src and not src.startswith("data:image"):
                image_urls.append(urljoin(base_url, src))

    # 6. Location
    raw_locations = article.get("locations")
    loc_data = article.get("location")
    if isinstance(raw_locations, list) and len(raw_locations) > 0 and isinstance(raw_locations[0], dict):
        loc0 = raw_locations[0]
        pref_dict = loc0.get("prefecture") or {}
        city_dict = loc0.get("city") or {}
        town_dict = loc0.get("town") or {}
        pref = (pref_dict.get("name_with_suffix") or pref_dict.get("name")) if isinstance(pref_dict, dict) else str(pref_dict)
        city = (city_dict.get("name_with_suffix") or city_dict.get("name")) if isinstance(city_dict, dict) else str(city_dict)
        town = (town_dict.get("name_with_suffix") or town_dict.get("name")) if isinstance(town_dict, dict) else str(town_dict)
        st_obj = loc0.get("station") or {}
        station = st_obj.get("name") if isinstance(st_obj, dict) else str(st_obj)
        m = loc0.get("map") or {}
        coord = (m.get("coordinate") or {}) if isinstance(m, dict) else {}
        lat = float(coord["latitude"]) if isinstance(coord, dict) and "latitude" in coord and coord["latitude"] is not None else None
        lng = float(coord["longitude"]) if isinstance(coord, dict) and "longitude" in coord and coord["longitude"] is not None else None
        area_name = m.get("area_name") if isinstance(m, dict) else None
        raw_loc = clean_text(area_name or loc0.get("area_name") or " - ".join(filter(None, [pref, city, town, station])))
    elif isinstance(loc_data, dict):
        pref = loc_data.get("prefecture") or loc_data.get("prefecture_name")
        city = loc_data.get("city") or loc_data.get("city_name")
        town = loc_data.get("town") or loc_data.get("town_name")
        station = loc_data.get("station") or loc_data.get("station_name")
        lat = float(loc_data["latitude"]) if "latitude" in loc_data and loc_data["latitude"] is not None else None
        lng = float(loc_data["longitude"]) if "longitude" in loc_data and loc_data["longitude"] is not None else None
        raw_loc = clean_text(loc_data.get("raw_text") or " - ".join(filter(None, [pref, city, station])))
    elif isinstance(loc_data, str):
        parsed = parse_location_hierarchy(loc_data)
        pref, city, town, station, lat, lng, raw_loc = (
            parsed.prefecture,
            parsed.city,
            parsed.town,
            parsed.station,
            parsed.latitude,
            parsed.longitude,
            parsed.raw_text,
        )
    else:
        pref = article.get("prefecture_name") or article.get("prefecture")
        city = article.get("city_name") or article.get("city") or article.get("municipality")
        town = article.get("town_name") or article.get("town")
        station = article.get("station_name") or article.get("station")
        lat = float(article["latitude"]) if "latitude" in article and article["latitude"] is not None else None
        lng = float(article["longitude"]) if "longitude" in article and article["longitude"] is not None else None
        raw_loc = clean_text(article.get("location_text") or article.get("address") or " - ".join(filter(None, [pref, city, station])))

    location = Location(
        prefecture=pref,
        city=city,
        town=town,
        station=station,
        latitude=lat,
        longitude=lng,
        raw_text=raw_loc,
    ) if (pref or city or station or raw_loc) else None

    # 7. Dates
    created_at = parse_datetime(article.get("created_at") or article.get("published_at"))
    updated_at = parse_datetime(article.get("updated_at") or article.get("modified_at"))
    if not created_at:
        date_el = soup.select_one("time, .p-article-date, [class*='date']")
        if date_el:
            created_at = parse_datetime(date_el.get("datetime") or date_el.get_text())

    # 8. Seller Profile
    seller = _parse_seller_profile(post_user, soup, base_url)

    # 9. Category & Status
    cat_obj = article.get("category")
    if isinstance(cat_obj, dict):
        cat_str = cat_obj.get("name") or cat_obj.get("slug")
    elif isinstance(cat_obj, str):
        cat_str = cat_obj
    else:
        cat_str = article.get("category_name")

    cat_path = article.get("category_path") or article.get("category_hierarchy") or []
    if isinstance(cat_path, str):
        cat_path = [cat_path]
    elif not cat_path and cat_str:
        cat_path = [cat_str]

    status = str(article.get("status") or article.get("state") or "open")

    return ListingDetail(
        id=item_id,
        title=title,
        url=full_url,
        price=price_val,
        price_text=price_text,
        description=description,
        image_urls=image_urls,
        location=location,
        location_text=raw_loc,
        created_at=created_at,
        updated_at=updated_at,
        seller=seller,
        category=cat_str,
        category_path=cat_path,
        status=status,
        is_free=is_free,
        attributes=article.get("attributes", {}),
        raw_data=article,
    )


def _parse_seller_profile(
    user_dict: Optional[Dict[str, Any]],
    soup: BeautifulSoup,
    base_url: str,
) -> SellerProfile:
    """Extract SellerProfile with verification badges and rating breakdown."""
    if not user_dict or not isinstance(user_dict, dict):
        user_dict = {}

    user_id = str(user_dict.get("id") or user_dict.get("user_id") or "")
    name = clean_text(
        user_dict.get("nickname")
        or user_dict.get("name")
        or user_dict.get("username")
        or ""
    )

    url = user_dict.get("url") or user_dict.get("profile_url")
    if url:
        profile_url = urljoin(base_url, url)
    elif user_id:
        profile_url = urljoin(base_url, f"/profiles/{user_id}")
    else:
        profile_url = None

    avatar_url = user_dict.get("avatar_url") or user_dict.get("icon_url")
    if avatar_url:
        avatar_url = urljoin(base_url, avatar_url)

    # Badge names list
    raw_badges = user_dict.get("badges") or user_dict.get("badge_names") or []
    badge_names: List[str] = []
    if isinstance(raw_badges, list):
        for b in raw_badges:
            if isinstance(b, str):
                badge_names.append(clean_text(b))
            elif isinstance(b, dict):
                badge_name = b.get("name") or b.get("title")
                if badge_name:
                    badge_names.append(clean_text(badge_name))

    cert_status = user_dict.get("certification_status")
    if isinstance(cert_status, dict):
        if cert_status.get("sms_authenticated") and "SMS認証済" not in badge_names:
            badge_names.append("SMS認証済")
        if (cert_status.get("identified") or cert_status.get("multi_identified")) and "本人確認済" not in badge_names:
            badge_names.append("本人確認済")
        if cert_status.get("antique_dealer_identified") and "古物商" not in badge_names:
            badge_names.append("古物商")
        if cert_status.get("business") and "法人" not in badge_names:
            badge_names.append("法人")

    # Identified badge check (本人確認済)
    identified = (
        bool(user_dict.get("identified"))
        or bool(user_dict.get("is_identified"))
        or (isinstance(cert_status, dict) and (bool(cert_status.get("identified")) or bool(cert_status.get("multi_identified"))))
        or user_dict.get("identification_state") == 2
        or user_dict.get("identification_status") in ("verified", "identified", 2)
        or any("本人確認" in b for b in badge_names)
    )

    # Antique dealer flag check (古物商 / 業者)
    is_antique_dealer = (
        bool(user_dict.get("is_antique_dealer"))
        or bool(user_dict.get("is_dealer"))
        or bool(user_dict.get("antique_dealer"))
        or (isinstance(cert_status, dict) and (bool(cert_status.get("antique_dealer_identified")) or bool(cert_status.get("business"))))
        or any("古物商" in b or "法人" in b for b in badge_names)
    )

    eval_dict = user_dict.get("evaluation")
    eval_count = eval_dict.get("count", {}) if isinstance(eval_dict, dict) and isinstance(eval_dict.get("count"), dict) else {}

    # Ratings extraction
    good_ratings = int(
        user_dict.get("good_evaluations_count")
        or user_dict.get("good_ratings")
        or user_dict.get("good_count")
        or user_dict.get("good")
        or eval_count.get("good_evaluation_count")
        or 0
    )
    normal_ratings = int(
        user_dict.get("normal_evaluations_count")
        or user_dict.get("normal_ratings")
        or user_dict.get("normal_count")
        or user_dict.get("normal")
        or eval_count.get("normal_evaluation_count")
        or 0
    )
    bad_ratings = int(
        user_dict.get("bad_evaluations_count")
        or user_dict.get("bad_ratings")
        or user_dict.get("bad_count")
        or user_dict.get("bad")
        or eval_count.get("bad_evaluation_count")
        or 0
    )
    total_ratings = int(
        user_dict.get("total_evaluations_count")
        or user_dict.get("total_ratings")
        or eval_dict.get("evaluation_score") if isinstance(eval_dict, dict) and eval_dict.get("evaluation_score") else 0
        or (good_ratings + normal_ratings + bad_ratings)
    )

    articles_count = int(
        user_dict.get("articles_count")
        or user_dict.get("open_articles_count")
        or user_dict.get("posts_count")
        or user_dict.get("active_articles_count")
        or 0
    )

    # HTML verification fallback if fields were missing from JSON
    if not name:
        user_el = soup.select_one(".p-user-name, .p-user-profile__name, [class*='seller'] [class*='name'], .user-name")
        if user_el:
            name = clean_text(user_el.get_text())

    if not identified:
        badge_el = soup.select_one(".badge-identified, [class*='badge-identified'], .p-user-profile__badge--identified, img[alt*='本人確認済']")
        if badge_el and "本人確認" in clean_text(badge_el.get_text()):
            identified = True
            if "本人確認済" not in badge_names:
                badge_names.append("本人確認済")
        elif soup.find(string=re.compile(r"本人確認済")):
            identified = True
            if "本人確認済" not in badge_names:
                badge_names.append("本人確認済")

    if not is_antique_dealer:
        dealer_el = soup.find(string=re.compile(r"古物商|法人出品"))
        if dealer_el:
            is_antique_dealer = True
            if "古物商許可" not in badge_names:
                badge_names.append("古物商許可")

    if good_ratings == 0 and bad_ratings == 0:
        good_el = soup.select_one(".rating-good, [class*='rating-good'], [class*='evaluation-good']")
        bad_el = soup.select_one(".rating-bad, [class*='rating-bad'], [class*='evaluation-bad']")
        if good_el:
            m = re.search(r"(\d+)", clean_text(good_el.get_text()))
            if m:
                good_ratings = int(m.group(1))
        if bad_el:
            m = re.search(r"(\d+)", clean_text(bad_el.get_text()))
            if m:
                bad_ratings = int(m.group(1))
        total_ratings = good_ratings + normal_ratings + bad_ratings

    return SellerProfile(
        id=user_id or None,
        name=name,
        url=profile_url,
        avatar_url=avatar_url,
        identified=identified,
        good_ratings=good_ratings,
        normal_ratings=normal_ratings,
        bad_ratings=bad_ratings,
        total_ratings=total_ratings,
        articles_count=articles_count,
        is_antique_dealer=is_antique_dealer,
        badge_names=badge_names,
        raw_profile=user_dict,
    )


def _parse_detail_from_html(soup: BeautifulSoup, raw_html: str, base_url: str) -> ListingDetail:
    """Fallback parser for detail pages when __NEXT_DATA__ is not present."""
    # 1. Title
    title_el = soup.select_one("h1, .p-article-header__title, .p-article-title, [class*='article-title']")
    title = clean_text(title_el.get_text()) if title_el else ""
    if not title:
        og_title = soup.select_one("meta[property='og:title']")
        if og_title and og_title.get("content"):
            title = clean_text(og_title["content"])

    # 2. Canonical URL & ID
    og_url = soup.select_one("meta[property='og:url'], link[rel='canonical']")
    full_url = og_url["href"] if (og_url and og_url.get("href")) else (og_url["content"] if og_url and og_url.get("content") else base_url)
    id_match = re.search(r"article[s]?-([a-zA-Z0-9]+)", full_url)
    item_id = id_match.group(1) if id_match else full_url.rstrip("/").split("/")[-1]
    if item_id in ("jmty.jp", ""):
        # Generate slug or fallback id
        item_id = f"article-{abs(hash(title)) % 100000}" if title else "article-unknown"

    # 3. Price
    price_el = soup.select_one(".p-article-header__price, .p-article-price, .price, [class*='price']")
    raw_price_str = clean_text(price_el.get_text()) if price_el else ""
    price_val, price_text, is_free = extract_price(raw_price_str)

    # 4. Description body
    body_el = soup.select_one(
        ".p-article-detail__body, .p-article-description, .p-article__content, [itemprop='description'], .article-body"
    )
    description = clean_text(body_el.get_text()) if body_el else ""

    # 5. Image URLs
    image_urls: List[str] = []
    for img in soup.select(".p-article-detail__images img, .p-article-images img, .image-gallery img, [class*='gallery'] img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if src and not src.startswith("data:image"):
            image_urls.append(urljoin(base_url, src))

    if not image_urls:
        og_img = soup.select_one("meta[property='og:image']")
        if og_img and og_img.get("content"):
            image_urls.append(urljoin(base_url, og_img["content"]))

    # 6. Location
    loc_el = soup.select_one(".p-article-header__location, .p-article-location, [class*='location']")
    loc_text = clean_text(loc_el.get_text()) if loc_el else None
    location = parse_location_hierarchy(loc_text) if loc_text else None

    # 7. Dates
    date_el = soup.select_one(".p-article-header__date, time, [class*='date']")
    date_text = clean_text(date_el.get_text()) if date_el else None
    created_at = parse_datetime(date_el.get("datetime")) if (date_el and date_el.get("datetime")) else parse_datetime(date_text)

    # 8. Seller Profile
    seller = _parse_seller_profile({}, soup, base_url)

    return ListingDetail(
        id=str(item_id),
        title=title,
        url=full_url,
        price=price_val,
        price_text=price_text,
        description=description,
        image_urls=image_urls,
        location=location,
        location_text=loc_text,
        created_at=created_at,
        seller=seller,
        is_free=is_free,
    )
