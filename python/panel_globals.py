# File Version: 1.0
from audio_runtime import AudioEndpointController
import os
import threading
import time
import uuid
import psutil
from collections import OrderedDict

# Project directories
PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PYTHON_DIR)
HTML_DIR = os.path.join(BASE_DIR, 'html')
JS_DIR = os.path.join(BASE_DIR, 'js')
JSON_DIR = os.path.join(BASE_DIR, 'json')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
FONTS_DIR = os.path.join(ASSETS_DIR, 'fonts')
IMAGES_DIR = os.path.join(ASSETS_DIR, 'images')
CSS_DIR = os.path.join(ASSETS_DIR, 'css')
PLUGINS_DIR = os.path.join(BASE_DIR, 'plugins')

# File Paths
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
RUNTIME_DIR = os.path.join(LOGS_DIR, 'runtime')
LOG_FILE = os.path.join(LOGS_DIR, 'logs.txt')
ERR_FILE = os.path.join(LOGS_DIR, 'errors.txt')
TUYA_LOG_FILE = os.path.join(LOGS_DIR, 'tuya.txt')
STARTUP_PROFILE_FILE = os.path.join(LOGS_DIR, 'startup_profile.txt')
HWINFO_LIVE_JSON = os.path.join(RUNTIME_DIR, 'hwinfo_live.json')
SHIFT_CACHE_XLSX = os.path.join(BASE_DIR, 'shift_cache.xlsx')
SHIFT_CACHE_META_JSON = os.path.join(JSON_DIR, 'shift_cache_meta.json')
WEBVIEW_DATA_DIR = os.path.join(LOGS_DIR, 'webview_data')
RESTART_GUARD_FILE = os.path.join(RUNTIME_DIR, 'restart_guard.json')

# Asset Paths
HTML_FILE_PATH = os.path.join(HTML_DIR, 'main.html')
HTML_VERTICAL_FILE_PATH = os.path.join(HTML_DIR, 'main2.html')
JS_FILE_PATH = os.path.join(JS_DIR, 'script.js')
LIQUID_THEMES_JS_FILE_PATH = os.path.join(JS_DIR, 'liquid_themes.js')
HATA_HTML_FILE_PATH = os.path.join(HTML_DIR, 'hata.html')
SITEMAP_HTML_FILE_PATH = os.path.join(HTML_DIR, 'sitemap.html')
SETTINGS_HTML_FILE_PATH = os.path.join(HTML_DIR, 'settings.html')
SETTINGS_I18N_JS_FILE_PATH = os.path.join(JS_DIR, 'settings_i18n.js')
SETTINGS_I18N_TR_JS_FILE_PATH = os.path.join(JS_DIR, 'settings_i18n_tr.js')
SETTINGS_I18N_EN_JS_FILE_PATH = os.path.join(JS_DIR, 'settings_i18n_en.js')
SETTINGS_THEME_LIGHT_CSS_FILE_PATH = os.path.join(CSS_DIR, 'settings-theme-light.css')
SETTINGS_THEME_DARK_CSS_FILE_PATH = os.path.join(CSS_DIR, 'settings-theme-dark.css')

# Headers
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

# Locks
SENSOR_CACHE_LOCK = threading.Lock()
SETTINGS_SNAPSHOT_LOCK = threading.Lock()
PUBLIC_STATUS_CACHE_LOCK = threading.Lock()
RUNTIME_THREADS_LOCK = threading.Lock()
LOG_CLEANUP_LOCK = threading.Lock()
STARTUP_PROFILE_LOCK = threading.Lock()
HWI_BINDINGS_LOCK = threading.Lock()
APP_RESTART_LOCK = threading.Lock()
REFRESH_LOCK = threading.Lock()
WS_CLIENTS_LOCK = threading.Lock()
HTTP_SESSION_LOCK = threading.Lock()
LYRICS_CACHE_LOCK = threading.Lock()
LYRICS_STATE_LOCK = threading.Lock()
MUTE_STATE_LOCK = threading.Lock()
TARGET_VOLUME_LOCK = threading.Lock()
WEATHER_FETCH_LOCK = threading.Lock()

# Events
SERVER_READY = threading.Event()
WEBVIEW_STARTED = threading.Event()
SYSTEM_CACHE_EVENT = threading.Event()
MEDIA_LOOP_READY = threading.Event()

# Shared State
SYSTEM_CACHE = {
    'cpu_percent': None, 'ram_percent': None, 'ram_used_gb': None,
    'gpu_util': None, 'gpu_temp': None, 'cpu_temp': None,
    'cpu_power': None, 'gpu_power': None, 'uptime': '-',
    'media_title': '', 'media_artist': '', 'media_position': 0,
    'media_duration': 0, 'media_is_playing': False,
    'lyrics': 'nihil infinitum est', 'volume_percent': None,
    'is_muted': None, 'fps': None, 'fps_1_low': None,
    'vram_percent': None, 'tuya_devices': [],
    'download_speed_mbps': None, 'upload_speed_mbps': None,
    'media_source_app': '',
    'media_track_token': '', 'motherboard_temp': None,
    'vmos_temp': None, 'mobo_temp': None, 'vrm_temp': None, 'vrmos_temp': None, 'ram_slot_temps': [], 'disks_cde': {}, 'hwinfo_temp_rows_debug': [],
    'tomorrow_shift_text': None, 'tomorrow_shift_subtitle': None,
    'last_update': 0, 'recent_issues': [], 'module_status': {},
}

WORKER_STATE = {
    'hwinfo_proc': None, 'last_hwinfo_seen': 0.0, 'last_hwinfo_restart': 0.0,
    'last_hwinfo_signature': None, 'last_hwinfo_app_restart_check_key': '',
    'last_hwinfo_app_restart_at': 0.0, 'last_hwinfo_app_restart_reason': '',
    'last_hwinfo_shared_memory_restart_at': 0.0,
}

PUBLIC_STATUS_CACHE = {'signature': None, 'payload': None}
LYRICS_CACHE = OrderedDict()
LYRICS_CACHE_MAX_ITEMS = 128
WS_CLIENTS = set()

# Webview
WINDOW_TITLE_BASE = 'PC Control Panel::__webview__::' + uuid.uuid4().hex[:8]
PANEL_WEBVIEW_WINDOW = None

# Boot time
BOOT_TIME_SEC = psutil.boot_time()

# Constants
PORT = 5001
URL_MODE = ''
WORKER_HEARTBEAT_TIMEOUT_SECONDS = 4.0
WORKER_RESTART_COOLDOWN_SECONDS = 2.0
HWINFO_SNAPSHOT_MAX_AGE_SECONDS = 8.0
HWINFO_SHARED_MEMORY_RESTART_COOLDOWN_SECONDS = 90.0
HWINFO_PROCESS_NAMES = {'hwinfo64.exe', 'hwinfo32.exe', 'hwinfo.exe'}
HWINFO_SNAPSHOT_EVENT_NAME = 'Local\\pc_control_hwinfo_snapshot_ready'
HWINFO_SNAPSHOT_MIN_STAT_SECONDS = 0.20
FPS_IGNORE_APPS = {'msedgewebview2', 'unknown', ''}
FALLBACK_STARTUP_ERROR_MIN_INTERVAL_SECONDS = 60.0
RESTART_GUARD_WINDOW_SECONDS = 300.0
RESTART_GUARD_MAX_ATTEMPTS = 5

# Settings Cache
SETTINGS_SNAPSHOT = {'data': None, 'last_refresh': 0.0}
SETTINGS_SNAPSHOT_TTL_SECONDS = 1.0

PUBLIC_STATUS_FIELDS = (
    "cpu_percent", "ram_percent", "ram_used_gb", "gpu_util", "gpu_temp",
    "cpu_temp", "cpu_power", "gpu_power", "uptime", "media_title",
    "media_artist", "media_position", "media_duration", "media_is_playing",
    "lyrics", "volume_percent", "is_muted", "fps",
    "fps_1_low", "vram_percent", "tuya_devices", "download_speed_mbps",
    "upload_speed_mbps", "media_source_app", "media_track_token",
    "motherboard_temp", "mobo_temp", "vmos_temp", "vrm_temp", "vrmos_temp", "ram_slot_temps", "disks_cde", "hwinfo_temp_rows_debug",
    "weather_ok", "weather_location", "weather_summary", "weather_min_c",
    "weather_max_c", "weather_error", "weather_current_c",
    "weather_feels_like_c", "weather_humidity_percent",
    "weather_pressure_hpa", "weather_wind_kmh", "weather_wind_direction",
    "weather_code", "pc_plug_power_w", "tomorrow_shift_text",
    "tomorrow_shift_subtitle",
)

# Paths for commands
DNSREDIR_CMD_DEFAULT = 'D:\\Program\\Goodbye\\turkey_dnsredir_alternative4_superonline.cmd'
NOLLIE_BRIGHTNESS_SCRIPT_DEFAULT = os.path.join(PLUGINS_DIR, 'nollie', 'nollie_brightness.py')
NOLLIE_STATE_PATH_DEFAULT = os.path.join(JSON_DIR, 'nollie', 'nollie_brightness_state.json')
LIAN_CONTROL_SCRIPT_DEFAULT = os.path.join(PLUGINS_DIR, 'lian', 'lconnect_control.py')
LIAN_PROFILE_PATH_DEFAULT = os.path.join(JSON_DIR, 'lian', 'lconnect_profiles.json')
LIAN_STATE_CACHE_PATH_DEFAULT = os.path.join(JSON_DIR, 'lian', 'last_lconnect_state.json')
LIAN_DATA_DIR_DEFAULT = 'C:\\ProgramData\\Lian-Li\\L-Connect 3'
LIAN_SERVICE_URL_DEFAULT = 'http://127.0.0.1:11021/'

# Runtime Control
APP_RESTARTING = False
RUNTIME_THREADS_STARTED = False
REFRESH_REQUESTED = False
SERVER_START_FAILED = None

HTTP_SESSIONS_BY_LOOP = {}

PC_PLUG_QUERY_CACHE = {'ts': 0.0, 'power_w': None}
PC_PLUG_QUERY_INTERVAL_SECONDS = 10.0
PC_PLUG_CLOUD_CACHE = {'ts': 0.0, 'power_w': None, 'status': None, 'error': None, 'source': None}
PC_PLUG_CLOUD_QUERY_INTERVAL_SECONDS = 60.0

MEDIA_POLL_ACTIVE_SECONDS = 1.25
MEDIA_POLL_IDLE_SECONDS = 3.0
MEDIA_POLL_ERROR_SECONDS = 5.0
VOLUME_SYNC_INTERVAL_SECONDS = 5.0
MEDIA_TIMELINE_UPDATE_SECONDS = 0.25
HWI_BINDING_REFRESH_SECONDS = 300.0
HWI_MISSING_FPS_BINDING_RETRY_SECONDS = 15.0
OFFLINE_TUYA_REFRESH_INTERVAL_SECONDS = 15.0
HWININFO_REFRESH_INTERVAL_SECONDS = 1.0
NETWORK_SPEED_REFRESH_INTERVAL_SECONDS = 0.0
MUTE_STATE_REFRESH_INTERVAL_SECONDS = 0.0
UPTIME_UPDATE_INTERVAL_SECONDS = 0.0
MUTE_WS_BURST_UNTIL_TS = 0.0
MEDIA_SESSION_MANAGER = None
LAST_SENT_MEDIA_TITLE = ''
CURRENT_TRACK_KEY = None
CURRENT_LYRICS = None
LYRICS_FETCHING = False

# Shared Instances
AUDIO_CONTROLLER = AudioEndpointController(logger=lambda msg: None)
PANEL_WINDOW_TITLE = 'PC Control Panel'

__all__ = [name for name in globals() if not name.startswith("__")]
