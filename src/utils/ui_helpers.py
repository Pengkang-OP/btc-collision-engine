"""UI helper utilities for console output formatting."""


def format_table(
    headers: list[str],
    rows: list[list[str]],
) -> str:
    """Format data as a simple ASCII table.

    Args:
        headers: Column header strings
        rows: List of row data

    Returns:
        Formatted table string
    """
    if not headers:
        return ""

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(
                    col_widths[i], len(str(cell))
                )

    sep = "+" + "+".join(
        "-" * (w + 2) for w in col_widths
    ) + "+"
    header_line = (
        "| "
        + " | ".join(
            h.ljust(w)
            for h, w in zip(headers, col_widths)
        )
        + " |"
    )

    lines = [sep, header_line, sep]
    for row in rows:
        line = (
            "| "
            + " | ".join(
                str(c).ljust(w)
                for c, w in zip(
                    row, col_widths
                )
            )
            + " |"
        )
        lines.append(line)
    lines.append(sep)

    return "\n".join(lines)


def truncate_middle(
    s: str, max_len: int = 40
) -> str:
    """Truncate string in the middle if too long.

    Args:
        s: Input string
        max_len: Maximum length

    Returns:
        Truncated string with '...' in middle if needed
    """
    if len(s) <= max_len:
        return s
    half = (max_len - 3) // 2
    return f"{s[:half]}...{s[-half:]}"
