import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text: str | None) -> str | None:
    if text is None:
        return None
    s = unescape(text)
    s = re.sub(r"</?(p|div|br|li|ul|ol)\s*[^>]*>", "\n", s, flags=re.IGNORECASE)
    s = _TAG_RE.sub("", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
