"""Data models for jimoty-cli: SearchQuery, Location, SellerProfile, ListingSummary, ListingDetail."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Location:
    """Represents hierarchical location information for a Jimoty listing."""

    prefecture: Optional[str] = None
    city: Optional[str] = None
    town: Optional[str] = None
    station: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SellerProfile:
    """Seller account details and reputation metrics."""

    id: Optional[str] = None
    name: str = ""
    url: Optional[str] = None
    avatar_url: Optional[str] = None
    identified: bool = False  # 本人確認済 badge
    good_ratings: int = 0     # 良い
    normal_ratings: int = 0   # 普通
    bad_ratings: int = 0      # 悪い
    total_ratings: int = 0
    articles_count: int = 0   # 投稿数 / 出品数
    is_antique_dealer: bool = False  # 古物商許可・法人・業者
    badge_names: List[str] = field(default_factory=list)
    raw_profile: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.total_ratings == 0:
            self.total_ratings = self.good_ratings + self.normal_ratings + self.bad_ratings

    @property
    def positive_ratio(self) -> float:
        """Ratio of good ratings over total ratings (0.0 to 1.0)."""
        if self.total_ratings <= 0:
            return 0.0
        return self.good_ratings / self.total_ratings

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["positive_ratio"] = round(self.positive_ratio, 4)
        return d


@dataclass
class ListingSummary:
    """Summary of a listing parsed from SSR search result listings."""

    id: str
    title: str
    url: str
    price: int  # 0 for free / 0円
    price_text: str
    thumbnail_url: Optional[str] = None
    location: Optional[Location] = None
    location_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at_text: Optional[str] = None
    is_free: bool = False
    category_name: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def image_url(self) -> Optional[str]:
        """Convenience alias for thumbnail_url."""
        return self.thumbnail_url

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            d["updated_at"] = self.updated_at.isoformat()
        return d


@dataclass
class ListingDetail:
    """Complete structured listing details extracted from __NEXT_DATA__ or HTML."""

    id: str
    title: str
    url: str
    price: int  # 0 for free / 0円
    price_text: str
    description: str  # raw description body
    image_urls: List[str] = field(default_factory=list)
    location: Optional[Location] = None
    location_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    seller: Optional[SellerProfile] = None
    category: Optional[str] = None
    category_path: List[str] = field(default_factory=list)
    status: str = "open"
    is_free: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def image_url(self) -> Optional[str]:
        """Convenience property returning the primary image URL."""
        return self.image_urls[0] if self.image_urls else None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            d["updated_at"] = self.updated_at.isoformat()
        return d


@dataclass
class SearchQuery:
    """Parameters for constructing Jimoty search URLs and queries."""

    prefecture: str = "kanagawa"
    category: str = "sale-bik"
    municipality: Optional[str] = "a-314-chigasaki"
    keyword: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    page: int = 1
    sort: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_params(self) -> Dict[str, Any]:
        """Convert query filters to HTTP GET query parameters."""
        params: Dict[str, Any] = {}
        if self.keyword:
            params["keyword"] = self.keyword
        if self.min_price is not None:
            params["min_price"] = self.min_price
        if self.max_price is not None:
            params["max_price"] = self.max_price
        if self.page and self.page > 1:
            params["page"] = self.page
        if self.sort:
            params["sort"] = self.sort
        return params
