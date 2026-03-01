"""Terminal formatting utilities for the debug CLI."""


def format_table(headers: list[str], rows: list[list[str]], min_col_width: int = 6) -> str:
    if not headers:
        return ""

    col_widths = [max(min_col_width, len(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)

    header_line = fmt.format(*headers)
    separator = "-" * len(header_line.rstrip())

    lines = [header_line, separator]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append(fmt.format(*padded[:len(headers)]))

    return "\n".join(lines)


def format_section_header(title: str, params: dict | None = None) -> str:
    lines = [f"\n=== {title} ==="]
    if params:
        for key, value in params.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def format_warning(message: str) -> str:
    return f"  ! WARNING: {message}"


def format_metric(name: str, value, unit: str = "", note: str = "") -> str:
    parts = [f"  {name}: {value}"]
    if unit:
        parts[0] += f" {unit}"
    if note:
        parts[0] += f"  ({note})"
    return parts[0]
