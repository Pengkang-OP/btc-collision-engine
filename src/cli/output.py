"""CLI output formatting utilities."""
import json


def format_results(results: list[dict]) -> str:
    """Format collision results for console output.

    Args:
        results: List of match result dicts

    Returns:
        Formatted output string
    """
    if not results:
        return "No matches found."

    lines = ["=== Collision Results ==="]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. Address: {r.get('address', 'N/A')}"
        )
    return "\n".join(lines)


def format_json(data) -> str:
    """Format data as pretty JSON.

    Args:
        data: Data to format

    Returns:
        Pretty JSON string
    """
    return json.dumps(data, indent=2, default=str)
