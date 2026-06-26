from urllib.parse import urlparse


def normalize_official_url(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    parsed = urlparse(cleaned)
    if not parsed.netloc:
        raise ValueError("Invalid official URL")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{host}{path}"
