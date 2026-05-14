# File Version: 1.0
import os
import time
import threading
from aiohttp import web
from panel_globals import (
    BASE_DIR, HTML_FILE_PATH, HTML_VERTICAL_FILE_PATH, IMAGES_DIR, FONTS_DIR, CSS_DIR, JS_DIR
)
from panel_logging import log_error

_HTML_RESPONSE_CACHE_LOCK = threading.Lock()
_HTML_RESPONSE_CACHE = {}
_TEXT_ASSET_CACHE_LOCK = threading.Lock()
_TEXT_ASSET_CACHE = {}
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

def _safe_static_file(root_dir: str, rel_path: str):
    """Statik dosyaları cache kapalı şekilde güvenli servis eder."""
    try:
        root_abs = os.path.abspath(root_dir)
        rel_path = str(rel_path or "").replace("\\", "/").lstrip("/")
        file_path = os.path.abspath(os.path.join(root_abs, rel_path))

        if not (file_path == root_abs or file_path.startswith(root_abs + os.sep)):
            return web.Response(status=403, text="Forbidden", headers=NO_CACHE_HEADERS)

        if not os.path.isfile(file_path):
            return web.Response(status=404, text="Not found", headers=NO_CACHE_HEADERS)

        return web.FileResponse(file_path, headers=NO_CACHE_HEADERS)
    except Exception as e:
        try:
            log_error(f"Static file serve error: {e}")
        except Exception:
            pass
        return web.Response(status=500, text=str(e), headers=NO_CACHE_HEADERS)


async def serve_resimler_no_cache(request):
    return _safe_static_file(IMAGES_DIR, request.match_info.get("path", ""))


async def serve_fonts_no_cache(request):
    return _safe_static_file(FONTS_DIR, request.match_info.get("path", ""))


async def serve_css_no_cache(request):
    return _safe_static_text_file(CSS_DIR, request.match_info.get("path", ""), "CSS asset", "text/css")


async def serve_js_no_cache(request):
    return _safe_static_text_file(JS_DIR, request.match_info.get("path", ""), "JavaScript asset", "application/javascript")

def _load_text_asset_response(path: str, label: str, content_type: str):
    try:
        try:
            stat = os.stat(path)
            mtime_ns = getattr(stat, "st_mtime_ns", None) or int(stat.st_mtime * 1_000_000_000)
        except Exception:
            mtime_ns = None

        with _TEXT_ASSET_CACHE_LOCK:
            cached = _TEXT_ASSET_CACHE.get(path)
            if cached and cached.get("mtime_ns") == mtime_ns:
                content = cached["content"]
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                _TEXT_ASSET_CACHE[path] = {"mtime_ns": mtime_ns, "content": content}

        return web.Response(text=content, content_type=content_type, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"{label} file could not be read: {e}")
        return web.Response(text=f"{label} an error occurred while loading: {e}", status=500)


def _safe_static_text_file(root_dir: str, rel_path: str, label: str, content_type: str):
    try:
        root_abs = os.path.abspath(root_dir)
        rel_path = str(rel_path or "").replace("\\", "/").lstrip("/")
        file_path = os.path.abspath(os.path.join(root_abs, rel_path))

        if not (file_path == root_abs or file_path.startswith(root_abs + os.sep)):
            return web.Response(status=403, text="Forbidden", headers=NO_CACHE_HEADERS)

        if not os.path.isfile(file_path):
            return web.Response(status=404, text="Not found", headers=NO_CACHE_HEADERS)

        response = _load_text_asset_response(file_path, label, content_type)
        if isinstance(response.text, str):
            response.text = response.text.replace("__ASSET_VERSION__", str(int(time.time())))
        return response
    except Exception as e:
        try:
            log_error(f"Static text file serve error: {e}")
        except Exception:
            pass
        return web.Response(status=500, text=str(e), headers=NO_CACHE_HEADERS)


def _load_html_response(path: str, label: str):
    try:
        try:
            stat = os.stat(path)
            mtime_ns = getattr(stat, "st_mtime_ns", None) or int(stat.st_mtime * 1_000_000_000)
        except Exception:
            stat = None
            mtime_ns = None

        with _HTML_RESPONSE_CACHE_LOCK:
            cached = _HTML_RESPONSE_CACHE.get(path)
            if cached and cached.get("mtime_ns") == mtime_ns:
                html_content = cached["content"]
            else:
                with open(path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                _HTML_RESPONSE_CACHE[path] = {"mtime_ns": mtime_ns, "content": html_content}

        current_version = str(int(time.time()))
        html_content = html_content.replace("__ASSET_VERSION__", current_version)

        return web.Response(
            text=html_content,
            content_type="text/html",
            headers=NO_CACHE_HEADERS
        )
    except Exception as e:
        log_error(f"{label} file could not be read: {e}")
        return web.Response(text=f"{label} an error occurred while loading: {e}", status=500)


async def root(r):
    return _load_html_response(HTML_FILE_PATH, "HTML UI")


async def root_dikey(r):
    return _load_html_response(HTML_VERTICAL_FILE_PATH, "Vertical HTML UI")

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.     
__all__ = [name for name in globals() if not name.startswith("__")]
