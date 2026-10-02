"""Culturally idiomatic Japanese communication templates for Jimoty (jmty.jp) marketplace interactions.

Implements polite keigo (敬語) templates tailored for Jimoty C2C vehicle and goods transactions:
- initial: First contact expressing intent to purchase or receive with direct in-person pickup (直接引き取り).
- paperwork: Verification of registration documents (廃車申告受付書/譲渡証明書), Jibaiseki insurance, keys, and mechanical status.
- schedule: Coordination of meetup schedule, inspection, and pickup logistics.

Complies with Jimoty etiquette, handling free (0円) items, anonymous sellers, and vehicle-specific context.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from jimoty.models import ListingDetail

TEMPLATE_TYPES: List[str] = ["initial", "paperwork", "schedule"]


def list_template_types() -> List[str]:
    """Return list of supported inquiry template types."""
    return list(TEMPLATE_TYPES)


def _get_seller_salutation(detail: ListingDetail) -> str:
    """Return polite salutation for the seller, falling back gracefully if missing."""
    if detail.seller and detail.seller.name and detail.seller.name.strip():
        name = detail.seller.name.strip()
        if name.endswith("様") or name.endswith("さま"):
            return name
        return f"{name}様"
    return "出品者様"


def _format_location_hint(detail: ListingDetail) -> str:
    """Format location hint from listing detail for logistics context."""
    if not detail.location:
        return detail.location_text or ""
    parts: List[str] = []
    if detail.location.prefecture:
        parts.append(detail.location.prefecture)
    if detail.location.city:
        parts.append(detail.location.city)
    if detail.location.station:
        parts.append(f"{detail.location.station}周辺")
    return " ".join(parts) if parts else (detail.location_text or "")


def _render_initial_template(detail: ListingDetail, **kwargs: Any) -> str:
    """Render initial inquiry message requesting direct in-person pickup with keigo."""
    salutation = _get_seller_salutation(detail)
    title = detail.title.strip() if detail.title else "ご出品の商品"
    is_free = bool(detail.is_free or (detail.price is not None and detail.price == 0))
    price_str = detail.price_text or (f"{detail.price:,}円" if detail.price is not None else "")
    price_display = f"（{price_str}）" if (not is_free and price_str) else ""
    pickup_method = kwargs.get("pickup_method", "直接引き取り")
    buyer_name = kwargs.get("buyer_name", "")
    closing_name = f"\n\n{buyer_name}" if buyer_name else ""

    loc_hint = _format_location_hint(detail)
    loc_mention = f"{loc_hint}まで" if loc_hint else "指定の場所まで"

    if is_free:
        intent_line = f"ご出品されている「{title}」を拝見し、ぜひお譲りいただきたくご連絡いたしました。"
        purpose_line = f"当方、{loc_mention}伺い【{pickup_method}】にて対応可能です。大切に活用させていただきます。"
    else:
        intent_line = f"ご出品されている「{title}」{price_display}を拝見し、購入を希望しております。"
        purpose_line = f"当方、{loc_mention}伺い【{pickup_method}】にて迅速にお引き取りすることが可能です。"

    # Check time-of-day greeting (Japan Standard Time)
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    greeting = "はじめまして。コメント失礼いたします。"
    if now_jst.hour >= 22 or now_jst.hour < 5:
        greeting = "はじめまして。夜分遅くにコメント失礼いたします。"
    elif 5 <= now_jst.hour < 8:
        greeting = "はじめまして。早朝にコメント失礼いたします。"

    # Check listing recency: if > 30 days old, add gentle availability check
    availability_line = ""
    last_dt = detail.updated_at or detail.created_at
    if last_dt:
        now_utc = datetime.now(timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=jst)
        diff_days = (now_utc - last_dt).total_seconds() / 86400.0
        if diff_days >= 30:
            availability_line = "掲載から少々お時間が経過しておりますが、現在もお手元にありお取引可能でしょうか？"

    lines = [
        f"{salutation}",
        "",
        greeting,
        intent_line,
    ]
    if availability_line:
        lines.append(availability_line)
    lines.extend([
        purpose_line,
        "日時候補や受け渡し場所など、出品者様のご都合に合わせて柔軟に対応させていただきます。",
        "",
        "もしお取引が可能でしたら、ご都合の良い日程や引き渡し方法についてご教示いただけますと幸いです。",
        "スムーズで安心できるお取引を心がけますので、何卒よろしくお願いいたします。" + closing_name,
    ])
    return "\n".join(lines)


def _render_paperwork_template(detail: ListingDetail, **kwargs: Any) -> str:
    """Render inquiry inquiring about documents, Jibaiseki insurance, keys, and defects."""
    salutation = _get_seller_salutation(detail)
    title = detail.title.strip() if detail.title else "ご出品の商品"
    buyer_name = kwargs.get("buyer_name", "")
    closing_name = f"\n\n{buyer_name}" if buyer_name else ""

    lines = [
        f"{salutation}",
        "",
        "お世話になっております。",
        f"ご出品されている「{title}」の購入を前向きに検討しております。",
        "",
        "引き取り後のスムーズな名義変更・登録手続きおよび車両状態の確認のため、以下の点についてご教示いただけますでしょうか。",
        "",
        "1. 登録・譲渡書類について",
        "   廃車申告受付書（または標識交付証明書）および譲渡証明書（押印済み）など、名義変更・新規登録に必要な書類はお揃いでしょうか。",
        "",
        "2. 自賠責保険について",
        "   自賠責保険の残存期間はございますでしょうか。（残っている場合、自賠責証明書原本のお引渡しは可能でしょうか）",
        "",
        "3. 鍵および備品について",
        "   純正鍵・スペアキーの本数について教えていただけますでしょうか。",
        "",
        "4. 現在把握されている不具合・現状について",
        "   説明欄の記載以外に、オイル漏れ、タイヤのひび割れ、灯火類の不灯など、事前に把握しておくべき点がございましたらご教示いただけますと幸いです。",
        "",
        "お手数をおかけいたしますが、お手すきの際にご確認のほどよろしくお願いいたします。" + closing_name,
    ]
    return "\n".join(lines)


def _render_schedule_template(detail: ListingDetail, **kwargs: Any) -> str:
    """Render schedule coordination message for on-site inspection and pickup."""
    salutation = _get_seller_salutation(detail)
    title = detail.title.strip() if detail.title else "ご出品の商品"
    buyer_name = kwargs.get("buyer_name", "")
    closing_name = f"\n\n{buyer_name}" if buyer_name else ""

    dates = kwargs.get("candidate_dates")
    if not dates:
        dates = [
            "・第一希望：ご都合の良い日時",
            "・第二希望：平日の夜間（19時以降）または土日祝日",
            "・第三希望：出品者様のご指定日時に調整可能",
        ]
    elif isinstance(dates, list):
        dates = [f"・{d}" if not d.startswith("・") else d for d in dates]

    dates_str = "\n".join(dates)

    loc_hint = _format_location_hint(detail)
    location_mention = f"（{loc_hint}、またはご都合の良い待ち合わせ場所）" if loc_hint else "（ご都合の良い待ち合わせ場所）"

    lines = [
        f"{salutation}",
        "",
        "お世話になっております。",
        f"「{title}」の現車確認および直接引き渡しの日程調整についてご連絡いたしました。",
        "",
        "現地にて実車の確認とお引き渡しをさせていただきたく存じます。",
        "当方の訪問可能な候補日程を下記に記載いたしますので、出品者様のご都合と照らし合わせてご検討いただけますでしょうか。",
        "",
        "【引き渡し・現車確認の候補日時】",
        dates_str,
        "",
        "【待ち合わせ場所】",
        f"出品者様ご指定の場所{location_mention}にお伺いいたします。",
        "（コンビニの駐車場や駅前ロータリー、ご自宅前など、ご都合の良い場所をご指示ください）",
        "",
        "当日は軽トラック等でのお引き取り（または自走）を予定しており、代金はその場で現金手渡し可能です。",
        "ご都合に合わない場合は、別の日時をご提案いただけますと幸いです。",
        "引き続き何卒よろしくお願いいたします。" + closing_name,
    ]
    return "\n".join(lines)


def generate_inquiry_template(
    detail: ListingDetail,
    template_type: str = "initial",
    **kwargs: Any,
) -> str:
    """Generate culturally idiomatic, polite Japanese inquiry message for Jimoty listings.

    Args:
        detail: The ListingDetail instance containing item and seller info.
        template_type: Type of message ('initial', 'paperwork', 'schedule').
        **kwargs: Optional dynamic overrides (buyer_name, candidate_dates, pickup_method, etc.).

    Returns:
        Formatted Japanese message string with appropriate keigo and dynamic values.

    Raises:
        ValueError: If template_type is not recognized.
    """
    clean_type = template_type.strip().lower()
    if clean_type in ("initial", "first", "contact"):
        return _render_initial_template(detail, **kwargs)
    elif clean_type in ("paperwork", "docs", "document", "documents"):
        return _render_paperwork_template(detail, **kwargs)
    elif clean_type in ("schedule", "pickup", "appointment", "coordination"):
        return _render_schedule_template(detail, **kwargs)
    else:
        valid_types = ", ".join(TEMPLATE_TYPES)
        raise ValueError(
            f"Unsupported template_type: '{template_type}'. Supported types: {valid_types}"
        )
