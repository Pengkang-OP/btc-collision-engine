"""CLI pagination utilities for displaying long lists."""


def paginate(
    items: list[str],
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[str], int, int]:
    """Paginate a list of items.

    Args:
        items: Full list of items
        page: Current page (1-indexed)
        page_size: Items per page

    Returns:
        (page_items, total_pages, current_page)

    """
    total = len(items)
    total_pages = max(
        1, (total + page_size - 1) // page_size,
    )
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    return items[start:end], total_pages, page


def format_page_header(
    page: int,
    total_pages: int,
    heading: str = "Items",
) -> str:
    """Format page header.

    Args:
        page: Current page
        total_pages: Total pages
        heading: Section heading

    Returns:
        Formatted header

    """
    return (
        f"=== {heading} "
        f"(Page {page}/{total_pages}) ==="
    )
