#!/usr/bin/env python3
"""Lightweight preview server — stdlib only, no deps."""

import fnmatch
import hashlib
import os
import subprocess
import tempfile
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlunparse, quote
from uuid import uuid4
from threading import Lock

PORT = int(os.environ.get("PORT", "8080"))
PREVIEW_JAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "services", "preview.jar")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "preview-cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# simple in-process lock per URL to avoid duplicate renders
_render_locks: dict[str, Lock] = {}
_locks_lock = Lock()

DEFAULT_ALLOWED_ORIGINS = ",".join([
    "localhost",
    "*.svc.cluster",
    "netlogo.org",
    "*.netlogo.org",
    "modelingcommons.org",
    "*.modelingcommons.org",
    "modelingcommons.com",
    "*.modelingcommons.com",
    "netlogoweb.org",
    "*.netlogoweb.org",
    "ccl.northwestern.edu",
])

ALLOWED_ORIGINS = [
    p.strip() for p in
    os.environ.get("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if p.strip()
]

def _is_origin_allowed(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    return any(fnmatch.fnmatch(hostname, pattern) for pattern in ALLOWED_ORIGINS)

def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def _get_render_lock(url: str) -> Lock:
    with _locks_lock:
        if url not in _render_locks:
            _render_locks[url] = Lock()
        return _render_locks[url]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != "/preview":
            return self._err(404, "not found")

        params = parse_qs(parsed.query)

        if "model_url" not in params:
            return self._err(400, "missing model_url param")

        model_url = params["model_url"][0]
        mu = urlparse(model_url)
        model_url = urlunparse(mu._replace(path=quote(mu.path)))

        if not model_url.endswith(".nlogox"):
            return self._err(400, "model_url must end with .nlogox")

        if not _is_origin_allowed(model_url):
            return self._err(403, f"origin not allowed: {urlparse(model_url).hostname}")

        # check cache
        cached = os.path.join(CACHE_DIR, _cache_key(model_url) + ".png")
        if os.path.exists(cached):
            return self._serve_png(cached)

        # render with per-URL lock to avoid duplicate work
        lock = _get_render_lock(model_url)
        with lock:
            # double-check after acquiring lock
            if os.path.exists(cached):
                return self._serve_png(cached)

            req_id = uuid4().hex
            work_dir = os.path.join(tempfile.gettempdir(), req_id)
            model_path = os.path.join(work_dir, "model.nlogox")
            preview_path = os.path.join(work_dir, "preview.png")

            try:
                os.makedirs(work_dir)
                urllib.request.urlretrieve(model_url, model_path)

                result = subprocess.run(
                    ["java", "-Djava.awt.headless=true", "-Duser.home=/tmp",
                     "-jar", PREVIEW_JAR, model_path, preview_path],
                    capture_output=True, timeout=120,
                    stdin=subprocess.DEVNULL,
                )
                if result.returncode != 0:
                    return self._err(500, f"preview.jar failed: {result.stderr.decode()}")

                # move to cache
                os.rename(preview_path, cached)
                return self._serve_png(cached)

            except urllib.error.URLError as e: # type: ignore
                return self._err(502, f"fetch failed: {e}")
            except subprocess.TimeoutExpired:
                return self._err(504, "preview.jar timed out")
            finally:
                for p in (model_path, preview_path):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                try:
                    os.rmdir(work_dir)
                except OSError:
                    pass

    def _serve_png(self, path: str) -> None:
        with open(path, "rb") as f:
            img = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(img)))
        self.end_headers()
        self.wfile.write(img)

    def _err(self, code: int, msg: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())


if __name__ == "__main__":
    print(f"listening on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()