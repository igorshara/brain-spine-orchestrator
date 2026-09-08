"""Статичний сервер для «Лабіринту для двох» — Railway / локальний запуск.

Без залежностей, тільки stdlib. Віддає файли з цієї теки:
  • index.html і решта коду — без кешу, щоб передеплой одразу було видно;
  • assets/ (фото, музика) — з довгим кешем, щоб під час гри нічого не тягнулося;
  • невідомі шляхи — назад на index.html (сторінка одна).

Запуск:  python3 server.py   →  http://localhost:8000
Railway: web: python3 server.py  (PORT приходить із середовища)
"""

from __future__ import annotations

import os
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ico": "image/x-icon",
}


class Handler(SimpleHTTPRequestHandler):
    """Serve the one-page app, with asset caching and an index fallback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def translate_path(self, path):
        rel = unquote(urlparse(path).path)
        rel = posixpath.normpath(rel).lstrip("/")
        # нічого вище кореня теки не віддаємо
        if rel.startswith("..") or os.path.isabs(rel):
            rel = ""
        full = os.path.join(HERE, rel) if rel else os.path.join(HERE, "index.html")
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.exists(full):
            full = os.path.join(HERE, "index.html")   # одна сторінка на всі шляхи
        return full

    def guess_type(self, path):
        return MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")

    def end_headers(self):
        path = self.translate_path(self.path)
        if "/assets/" in path.replace(os.sep, "/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        """Мовчимо: у логах не має бути ані шляхів, ані кодів."""


def main():
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"labirynt: http://localhost:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
