# Ver. 0.7

import os
import queue
import re
import threading
import time
from collections import deque


def _repair_mojibake_text(text: str) -> str:
    value = str(text or "")
    suspicious_markers = ("Ã", "Å", "Ä", "â", "Â")
    if not any(marker in value for marker in suspicious_markers) and _mojibake_score(value) <= 0:
        return value

    repaired = value
    for _ in range(2):
        try:
            candidate = repaired.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
        except Exception:
            break
        if candidate == repaired:
            break
        if _mojibake_score(candidate) >= _mojibake_score(repaired):
            break
        repaired = candidate
    return repaired


def _mojibake_score(value: str) -> int:
    text = str(value or "")
    markers = ("Ã", "Å", "Ä", "â", "Â", "�")
    return sum(text.count(marker) for marker in markers)


_LOG_TRANSLATION_REPLACEMENTS = [
    ("hwinfo sensör eşleşmeleri başarıyla oluşturuldu.", "HWiNFO sensor bindings created successfully."),
    ("sensör eşleşmeleri başarıyla oluşturuldu.", "sensor bindings created successfully."),
    ("sensör eşleşmeleri", "sensor bindings"),
    ("başarıyla oluşturuldu", "created successfully"),
    ("başlangıç eşleşme hatası", "initial binding error"),
    ("eşleşme hatası", "binding error"),
    ("süreç başlatıldı", "process started"),
    ("worker süreç başlatıldı", "worker process started"),
    ("döngü hatası", "loop error"),
    ("güncelleme hatası", "update error"),
    ("ölçüm hatası", "measurement error"),
    ("başlatma hatası", "startup error"),
    ("yeniden başlatılıyor", "restarting"),
    ("yeniden başlatma hatası", "restart error"),
    ("durum okuma", "status read"),
    ("aktif medya bulunamadı", "no active media found"),
    ("şarkı", "song"),
    ("sözler", "lyrics"),
    ("açılış hatası", "launch error"),
    ("bağlı", "connected"),
    ("koptu", "disconnected"),
    ("güncellendi", "updated"),
    ("hazır", "ready"),
    ("uyarı", "warning"),
    ("hata", "error"),
    ("başlatıldı", "started"),
    ("başlatılamadı", "could not start"),
    ("oluşturuldu", "created"),
    ("bulunamadı", "not found"),
    ("okunamadı", "could not be read"),
    ("yüklenemedi", "could not be loaded"),
    ("kapatıldı", "closed"),
    ("açık", "open"),
    ("kapalı", "closed"),
    ("süreç", "process"),
    ("pencere", "window"),
    ("cihaz", "device"),
    ("bağlantı", "connection"),
    ("başarısız", "failed"),
    ("hwi̇nfo sensör eşleşmeleri başarıyla oluşturuldu.", "HWiNFO sensor bindings created successfully."),
    ("sensör eşleşmeleri başarıyla oluşturuldu.", "sensor bindings created successfully."),
    ("sensör eşleşmeleri", "sensor bindings"),
    ("başarıyla oluşturuldu", "created successfully"),
    ("başlangıç eşleşme hatası", "initial binding error"),
    ("eşleşme hatası", "binding error"),
    ("süreç başlatıldı", "process started"),
    ("worker süreç başlatıldı", "worker process started"),
    ("döngü hatası", "loop error"),
    ("güncelleme hatası", "update error"),
    ("ölçüm hatası", "measurement error"),
    ("başlatma hatası", "startup error"),
    ("yeniden başlatılıyor", "restarting"),
    ("yeniden başlatma hatası", "restart error"),
    ("durum okuma", "status read"),
    ("aktif medya bulunamadı", "no active media found"),
    ("şarkı", "song"),
    ("sözler", "lyrics"),
    ("açılış hatası", "launch error"),
    ("bağlı", "connected"),
    ("koptu", "disconnected"),
    ("güncellendi", "updated"),
    ("hazır", "ready"),
    ("uyarı", "warning"),
    ("hata", "error"),
    ("başlatıldı", "started"),
    ("başlatılamadı", "could not start"),
    ("oluşturuldu", "created"),
    ("bulunamadı", "not found"),
    ("okunamadı", "could not be read"),
    ("yüklenemedi", "could not be loaded"),
    ("kapatıldı", "closed"),
    ("açık", "open"),
    ("kapalı", "closed"),
    ("süreç", "process"),
    ("pencere", "window"),
    ("cihaz", "device"),
    ("bağlantı", "connection"),
    ("başarısız", "failed"),
]

_LOG_TRANSLATION_REPLACEMENTS = list(dict.fromkeys(_LOG_TRANSLATION_REPLACEMENTS))
_COMPILED_LOG_TRANSLATION_REPLACEMENTS = [
    (re.compile(re.escape(old), re.IGNORECASE), old.lower(), new)
    for old, new in _LOG_TRANSLATION_REPLACEMENTS
]


def _translate_log_text(text: str) -> str:
    value = _repair_mojibake_text(text)
    lowered = value.lower()
    changed = False
    for pattern, needle, new in _COMPILED_LOG_TRANSLATION_REPLACEMENTS:
        if needle in lowered:
            value = pattern.sub(new, value)
            lowered = value.lower()
            changed = True
    return value if changed else value

class AsyncLineLogger:
    def __init__(
        self,
        log_file: str,
        err_file: str,
        max_lines: int = 1500,
        cleanup_interval_seconds: float = 900.0,
        max_queue_size: int = 5000,
    ):
        self.log_file = log_file
        self.err_file = err_file
        self.max_lines = int(max_lines)
        self.cleanup_interval_seconds = float(cleanup_interval_seconds)
        self._queue = queue.Queue(maxsize=max(100, int(max_queue_size)))
        self._last_cleanup_at = {}
        self._cleanup_lock = threading.Lock()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="async-line-logger")
        self._thread.start()

    def _prune_log_file(self, path: str, force: bool = False):
        now = time.time()
        with self._cleanup_lock:
            last_cleanup = float(self._last_cleanup_at.get(path) or 0.0)
            if not force and (now - last_cleanup) < self.cleanup_interval_seconds:
                return
            self._last_cleanup_at[path] = now
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tail = deque(f, maxlen=self.max_lines)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(tail)
            os.replace(tmp_path, path)
        except Exception:
            pass

    def _format_line(self, text: str):
        text = _translate_log_text(text)
        return f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {text}\n"

    def _write_lines_now(self, path: str, lines):
        if not path or not lines:
            return
        try:
            self._prune_log_file(path)
            parent_dir = os.path.dirname(path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass

    def _worker(self):
        batch_max = 250
        batch_wait_seconds = 0.25
        while True:
            path, text = self._queue.get()
            if path is None:
                return

            grouped = {path: [self._format_line(text)]}
            deadline = time.time() + batch_wait_seconds

            while len(grouped.get(path, [])) < batch_max:
                timeout = max(0.0, deadline - time.time())
                if timeout <= 0:
                    break
                try:
                    next_path, next_text = self._queue.get(timeout=timeout)
                except queue.Empty:
                    break
                if next_path is None:
                    for out_path, lines in grouped.items():
                        self._write_lines_now(out_path, lines)
                    return
                grouped.setdefault(next_path, []).append(self._format_line(next_text))
                if sum(len(lines) for lines in grouped.values()) >= batch_max:
                    break

            for out_path, lines in grouped.items():
                self._write_lines_now(out_path, lines)

    def _enqueue(self, path: str, text: str):
        item = (path, text)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except Exception:
                pass
            try:
                self._queue.put_nowait(item)
            except Exception:
                pass

    def log(self, text: str):
        self._enqueue(self.log_file, text)

    def error(self, text: str):
        self._enqueue(self.err_file, text)

    def prune_all_now(self):
        for path in (self.log_file, self.err_file):
            self._prune_log_file(path, force=True)
