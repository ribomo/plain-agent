"""Helpers for safely displaying untrusted text."""


def escape_display_text(value: str) -> str:
    """Escape control characters and backslashes for safe, unambiguous display."""
    escaped: list[str] = []
    for character in value:
        if character == "\\":
            escaped.append("\\\\")
        elif character.isprintable():
            escaped.append(character)
        else:
            escaped.append(ascii(character)[1:-1])
    return "".join(escaped)
