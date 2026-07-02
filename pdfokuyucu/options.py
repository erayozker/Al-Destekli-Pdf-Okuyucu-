from __future__ import annotations

from flask import Request

from .config import SEARCH_MODES, SUMMARY_LENGTHS, THEMES


def parse_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value or default)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def parse_float(value: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value or default)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def checkbox(request: Request, name: str) -> bool:
    return request.args.get(name) in {"1", "true", "on", "yes"}


def current_options(request: Request) -> dict[str, object]:
    summary_length = request.args.get("summary", "medium")
    if summary_length not in SUMMARY_LENGTHS:
        summary_length = "medium"

    theme = request.args.get("theme", "light")
    if theme not in THEMES:
        theme = "light"

    search_mode = request.args.get("search_mode", "exact")
    if search_mode not in SEARCH_MODES:
        search_mode = "exact"

    return {
        "query": request.args.get("q", "").strip(),
        "summary_length": summary_length,
        "keyword_limit": parse_int(request.args.get("keywords"), 10, 3, 30),
        "zoom": parse_float(request.args.get("zoom"), 1.6, 0.8, 3.0),
        "theme": theme,
        "case_sensitive": checkbox(request, "case_sensitive"),
        "whole_word": checkbox(request, "whole_word"),
        "search_mode": search_mode,
        "page_from": parse_int(request.args.get("page_from"), 1, 1, 99999),
        "page_to": parse_int(request.args.get("page_to"), 99999, 1, 99999),
        "selected_text": request.args.get("selected_text", "").strip(),
    }


def option_args(options: dict[str, object]) -> dict[str, object]:
    return {
        "q": options["query"],
        "summary": options["summary_length"],
        "keywords": options["keyword_limit"],
        "zoom": options["zoom"],
        "theme": options["theme"],
        "case_sensitive": "1" if options["case_sensitive"] else "",
        "whole_word": "1" if options["whole_word"] else "",
        "search_mode": options["search_mode"],
        "page_from": options["page_from"],
        "page_to": options["page_to"],
    }
