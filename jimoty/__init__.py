"""jimoty-cli: Python library and CLI for searching, scraping, and analyzing Japan Jimoty (jmty.jp) listings."""

from jimoty.checklist import (
    ChecklistItem,
    get_pickup_checklist,
    render_checklist_markdown,
    render_checklist_terminal,
)
from jimoty.cli import main, main as cli_main
from jimoty.client import (
    BlockedError,
    ChunkedTransferError,
    JimotyClient,
    JimotyError,
    JimotyNetworkError,
    ListingNotFoundError,
    ProxyError,
    RateLimitError,
    build_search_url,
)
from jimoty.config import (
    BASE_URL,
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_MAX_PRICE,
    DEFAULT_MUNICIPALITY,
    DEFAULT_PREFECTURE,
    MUNICIPALITIES,
    JimotyConfig,
    resolve_category,
    resolve_municipality,
    resolve_proxy,
)
from jimoty.diagnostics import (
    DiagnosticEngine,
    DiagnosticReport,
    RuleCategory,
    RuleSeverity,
    Verdict,
)
from jimoty.models import (
    ListingDetail,
    ListingSummary,
    Location,
    SearchQuery,
    SellerProfile,
)
from jimoty.parser import (
    ParserError,
    clean_text,
    extract_price,
    parse_detail_page,
    parse_search_page,
)
from jimoty.templates import (
    generate_inquiry_template,
    list_template_types,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "SearchQuery",
    "ListingSummary",
    "ListingDetail",
    "Location",
    "SellerProfile",
    # Config
    "JimotyConfig",
    "BASE_URL",
    "DEFAULT_PREFECTURE",
    "DEFAULT_MUNICIPALITY",
    "DEFAULT_CATEGORY",
    "DEFAULT_MAX_PRICE",
    "MUNICIPALITIES",
    "CATEGORIES",
    "resolve_proxy",
    "resolve_municipality",
    "resolve_category",
    # Client & Exceptions
    "JimotyClient",
    "build_search_url",
    "JimotyError",
    "JimotyNetworkError",
    "RateLimitError",
    "BlockedError",
    "ListingNotFoundError",
    "ChunkedTransferError",
    "ProxyError",
    # Parser
    "parse_search_page",
    "parse_detail_page",
    "extract_price",
    "clean_text",
    "ParserError",
    # Diagnostics
    "DiagnosticEngine",
    "DiagnosticReport",
    "Verdict",
    "RuleSeverity",
    "RuleCategory",
    # Cultural Templates
    "generate_inquiry_template",
    "list_template_types",
    # Pickup Safety Checklist
    "get_pickup_checklist",
    "ChecklistItem",
    "render_checklist_markdown",
    "render_checklist_terminal",
    # CLI
    "main",
    "cli_main",
]
