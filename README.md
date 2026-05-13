<!-- File Version: 1.0 -->
# PC Control Panel

A personal Windows-based PC monitoring, control, and automation dashboard.

This panel brings together hardware monitoring, media controls, smart home devices, weather, shift information, external Spotify/YouTube windows, system power controls, logs, health checks, and a full settings interface in one local dashboard.

It is designed for use on a second screen, small HDMI display, in-case display, desktop control monitor, or always-on information panel.

Panel Demo

<img width="1991" height="1175" alt="image" src="https://github.com/user-attachments/assets/8603d78f-a7da-453b-bca7-e9bee2b12ea8" />

Settings Demo

<img width="2557" height="1225" alt="image" src="https://github.com/user-attachments/assets/cc666f1f-3728-468f-b810-c4b81024ce4f" />



---

## Table of Contents

- [Overview](#overview)
- [Main Features](#main-features)
- [Displayed Information](#displayed-information)
- [Settings System](#settings-system)
- [Settings Page](#settings-page)
- [System Monitoring](#system-monitoring)
- [HWiNFO Integration](#hwinfo-integration)
- [Media Control](#media-control)
- [Lyrics](#lyrics)
- [Tuya Integration](#tuya-integration)
- [SmartThings Climate Control](#smartthings-climate-control)
- [Weather](#weather)
- [Shift System](#shift-system)
- [Panel Buttons](#panel-buttons)
- [External Windows](#external-windows)
- [Visual System](#visual-system)
- [Health, Logs, and Sitemap](#health-logs-and-sitemap)
- [API Endpoints](#api-endpoints)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running](#running)
- [File Structure](#file-structure)
- [Security Notes](#security-notes)
- [License](#license)

---

# Overview

This project is a personal control center built with a Python backend, an HTML/CSS/JavaScript frontend, and Windows system APIs.

The backend uses `aiohttp` for HTTP routes and WebSocket broadcasting. The frontend is handled by `main.html` and `script.js`. Configuration is stored in `settings.json` and can be edited through the built-in settings page.

The main purpose of the panel is to:

- Monitor PC hardware status in real time
- Display CPU, GPU, RAM, FPS, power, temperature, network, and uptime information
- Control media playback
- Manage system volume and mute state
- Display lyrics for the currently playing song
- Control Tuya smart devices
- Track PC smart plug wattage
- Control a SmartThings-compatible climate device
- Display weather information
- Read and display Excel/SharePoint-based shift information
- Launch separate Spotify and YouTube Shorts WebView windows
- Run system commands such as shutdown, restart, sleep, Task Manager, and custom commands
- Monitor panel health and logs
- Customize behavior through a full settings interface

---

# Main Features

- Real-time PC monitoring dashboard
- HWiNFO sensor integration
- CPU temperature monitoring
- CPU power monitoring
- GPU temperature monitoring
- GPU usage monitoring
- GPU power monitoring
- RAM usage monitoring
- VRAM usage and temperature fields
- FPS and 1% low FPS display
- FPS source application detection
- Network download/upload speed
- System uptime display
- Motherboard temperature field
- VMOS temperature field
- RAM slot temperature fields
- Disk temperature fields
- Estimated total system power
- Tuya smart device control
- PC smart plug wattage tracking
- SmartThings climate control popup
- Open-Meteo weather integration
- Excel/SharePoint shift reader
- Windows media control
- Lyrics support
- Seekbar support
- System volume knob
- Mute control
- Customizable panel buttons
- Separate Spotify WebView window
- Separate YouTube Shorts WebView window
- Full settings page
- Health report page
- Logs page
- Sitemap page
- WebSocket live status broadcasting
- Configurable polling and refresh intervals
- Low performance mode
- Liquid animation system
- Turkish / English panel language support

---

# Displayed Information

The main dashboard can display the following information.

## Top Cards

- CPU temperature
- CPU power draw
- GPU temperature
- GPU usage
- GPU power draw
- RAM usage
- FPS
- 1% low FPS
- Shift information
- Estimated total system power

## System Information Area

- Date
- Time
- Weather summary
- Location
- Motherboard temperature
- VMOS temperature
- System uptime
- Upload speed
- Download speed
- Disk temperatures
- RAM slot temperatures
- VRAM usage
- VRAM temperature
- FPS source application
- PC plug wattage
- Total system power source information

## Media Area

- Track title
- Artist name
- Album art
- Media source application
- Playback state
- Current playback position
- Track duration
- Seekbar
- Lyrics
- Custom idle media text
- No-media placeholder text

## Tuya Area

- Visible Tuya devices
- Device name
- On/off state
- Brightness value
- Pending command state
- Device error state
- PC plug wattage

## Control Area

- Volume level
- Mute state
- Previous track
- Play/pause
- Next track
- Shortcut buttons
- Climate popup
- YouTube launch/kill buttons
- Spotify launch/kill buttons
- System power controls

---

# Settings System

Panel settings are read from `settings.json`.

Default settings are defined in `settings_runtime.py`.

Main settings groups:

```json
{
  "performance": {},
  "frontend": {},
  "window": {},
  "tuya": {},
  "logging": {},
  "startup": {},
  "api": {},
  "external_windows": {},
  "power": {},
  "hwinfo": {},
  "commands": {},
  "panel": {}
}
```

## Main Setting Categories

| Category | Purpose |
|---|---|
| `performance` | Refresh intervals, polling speeds, retry counts |
| `frontend` | UI visibility, language, animations, media behavior |
| `window` | Panel window size, monitor, port, always-on-top behavior |
| `tuya` | Tuya device visibility, timeouts, read mode, brightness behavior |
| `logging` | Debug logs, WebSocket logs, Tuya/HWiNFO logs, cleanup behavior |
| `startup` | Startup-related behavior |
| `api` | Open-Meteo, Tuya Cloud, SmartThings, shift API settings |
| `external_windows` | Spotify and YouTube WebView window settings |
| `power` | Additional system power estimation |
| `hwinfo` | HWiNFO executable path, auto restart, FPS ignore list |
| `commands` | Custom executable/script commands |
| `panel` | Custom panel buttons |

---

# Settings Page

The settings page is available at:

```txt
http://localhost:5001/settings
```

The settings interface contains the following sections:

- Home
- Performance
- Media
- Appearance
- Effects
- Buttons
- Tuya
- Services
- Calendar
- Health
- Logs
- Sitemap
- Reset

---

## Home

The Home section shows a general settings overview and save status.

Typical purpose:

- Confirm that the settings page is loaded
- View general panel state
- Save edited settings
- Restart/refresh panel-related services when needed

---

## Performance

Controls update and polling intervals.

Fields include:

- UI update interval
- WebSocket broadcast interval
- Status poll interval
- HWiNFO refresh interval
- HWiNFO cache read interval
- Media refresh interval
- Volume refresh interval
- Mute refresh interval
- FPS refresh interval
- Weather refresh interval
- Shift cache check interval
- Network refresh interval
- Uptime refresh interval
- Tuya refresh interval
- Tuya retry count
- Other system power estimate

Example:

```json
{
  "performance": {
    "ui_update_interval_ms": 250,
    "websocket_broadcast_interval_ms": 250,
    "status_poll_interval_ms": 500,
    "hwinfo_refresh_interval_ms": 1000,
    "hwinfo_cache_read_interval_ms": 500,
    "media_refresh_interval_ms": 500,
    "volume_refresh_interval_ms": 250,
    "mute_refresh_interval_ms": 250,
    "fps_refresh_interval_ms": 500,
    "weather_refresh_interval_minutes": 30,
    "shift_cache_check_interval_minutes": 30,
    "network_refresh_interval_ms": 5000,
    "uptime_refresh_interval_ms": 5000,
    "tuya_refresh_interval_ms": 5000,
    "tuya_retry_count": 1
  }
}
```

---

## Media

Controls media playback display and behavior.

Fields include:

- Seekbar update interval
- Lyrics refresh interval
- Media progress interval while playing
- Media progress interval while paused
- Lyrics animation interval
- Lyric offset
- Idle text
- No-media placeholder title
- Lyrics waiting text
- Hide seekbar when idle
- Show media progress when idle
- Show now playing card
- Show lyrics card

Example:

```json
{
  "frontend": {
    "seekbar_update_interval_ms": 250,
    "lyrics_refresh_interval_ms": 1000,
    "media_progress_interval_playing_ms": 150,
    "media_progress_interval_paused_ms": 500,
    "lyrics_animation_interval_ms": 150,
    "lyric_offset_sec": 0.8,
    "idle_text": "nihil infinitum est | el. psy. congroo",
    "no_media_placeholder_title": "el. psy. congroo.",
    "lyrics_waiting_text": "Waiting for lyrics...",
    "hide_seekbar_when_idle": true,
    "show_media_progress_when_idle": false,
    "show_now_playing_card": true,
    "show_lyrics_card": true
  }
}
```

---

## Appearance

Controls the panel window and display behavior.

Fields include:

- Panel port
- Window title
- Target monitor device
- Monitor left position
- Monitor top position
- Monitor width
- Monitor height
- Always on top
- Hide from taskbar
- Layout mode
- Panel width
- Panel height
- Keep window alive interval
- Keep window minimum interval

Example:

```json
{
  "window": {
    "port": 5001,
    "title": "Kontrol Paneli",
    "target_monitor_device": "",
    "target_monitor_left": 0,
    "target_monitor_top": 0,
    "target_monitor_width": 1920,
    "target_monitor_height": 1080,
    "always_on_top": true,
    "keep_window_alive_interval_ms": 2000,
    "keep_window_alive_min_interval_ms": 250,
    "hide_from_taskbar": true,
    "layout_mode": "landscape",
    "panel_width": 1280,
    "panel_height": 800
  }
}
```

---

## Effects

Controls visual effects and liquid animation behavior.

Fields include:

- Liquid animation enabled
- Liquid animation FPS
- Liquid animation mode
- Liquid wave when idle
- CPU liquid theme
- GPU liquid theme
- RAM liquid theme
- FPS liquid theme
- Power liquid theme
- Shift liquid theme
- Animation level
- Low performance mode

Example:

```json
{
  "frontend": {
    "liquid_animation_enabled": true,
    "liquid_animation_fps": 16,
    "liquid_animation_mode": "light",
    "liquid_wave_when_idle": false,
    "liquid_theme_cpu": "default_glass",
    "liquid_theme_gpu": "default_glass",
    "liquid_theme_ram": "default_glass",
    "liquid_theme_fps": "default_glass",
    "liquid_theme_power": "default_glass",
    "liquid_theme_shift": "default_glass",
    "animation_level": "normal",
    "low_performance_mode": false
  }
}
```

---

## Buttons

Controls the customizable panel shortcut buttons.

Each button supports:

- ID
- Label
- Visibility
- Style variant
- Primary command
- Secondary command
- HTTP method
- Confirmation text
- SVG icon

Example button:

```json
{
  "id": "taskmgr",
  "label": "Task Manager",
  "visible": true,
  "variant": "white-glow",
  "command": "/taskmgr",
  "secondary_command": "",
  "method": "GET",
  "confirm_text": "",
  "icon_svg": "<svg></svg>"
}
```

Supported method values:

```txt
GET
POST
SPECIAL
```

Default button examples:

- Admin CMD
- DNS Redir
- Climate
- Task Manager
- YouTube
- Spotify
- Sleep
- Restart
- Shutdown

Button capabilities:

- Show or hide button
- Change label
- Change SVG icon
- Change style variant
- Assign a primary command
- Assign a secondary command
- Add confirmation text
- Trigger special popup actions such as climate control

---

## Tuya

Controls smart device behavior.

Fields include:

- Visible device keys
- PC plug key
- Brightness popup timeout
- Read mode
- Device timeout
- Local command timeout
- Cloud command timeout
- Max parallel status workers
- Status batch size

Example:

```json
{
  "tuya": {
    "visible_device_keys": [],
    "pc_plug_key": "",
    "brightness_popup_timeout_ms": 1600,
    "read_mode": "local",
    "device_timeout_ms": 2500,
    "local_command_timeout_ms": 2500,
    "cloud_command_timeout_ms": 8000,
    "max_parallel_status_workers": 4,
    "status_batch_size": 8
  }
}
```

Tuya actions:

- Check Tuya devices
- Reset Tuya runtime/pool
- Clear Tuya logs
- Toggle device
- Set brightness
- Read PC plug wattage

---

## Services

Controls external API services.

Service groups:

- Open-Meteo
- Tuya Cloud
- SmartThings

### Open-Meteo Settings

```json
{
  "api": {
    "meteo": {
      "forecast_url": "https://api.open-meteo.com/v1/forecast",
      "geocoding_url": "https://geocoding-api.open-meteo.com/v1/search",
      "location_query": "Kayseri",
      "location_label": "Kayseri",
      "latitude": 38.7205,
      "longitude": 35.4826,
      "timezone": "Europe/Istanbul",
      "language": "en"
    }
  }
}
```

### Tuya Cloud Settings

```json
{
  "api": {
    "tuya": {
      "base_url": "https://openapi.tuyaeu.com",
      "access_id": "",
      "access_secret": ""
    }
  }
}
```

### SmartThings Settings

```json
{
  "api": {
    "smartthings": {
      "api_key": "",
      "base_url": "https://api.smartthings.com/v1",
      "location_id": "",
      "device_id": "",
      "oauth_client_id": "",
      "oauth_client_secret": "",
      "oauth_refresh_token": "",
      "oauth_access_token": "",
      "oauth_access_token_expires_at": 0,
      "oauth_redirect_uri": ""
    }
  }
}
```

---

## Calendar

Controls the shift reader.

Fields include:

- Shared Excel/SharePoint URL
- Sheet name
- Employee name
- Name column
- Date row

Example:

```json
{
  "api": {
    "shift": {
      "share_url": "",
      "sheet_name": "Shift",
      "employee_name": "",
      "name_column": 3,
      "date_row": 2
    }
  }
}
```

---

## Health

Displays panel health status.

Health checks may include:

- HWiNFO worker status
- HWiNFO application status
- Tuya devices
- PC plug wattage
- Weather service
- SmartThings climate status
- Media session
- System cache
- WebSocket broadcast
- Runtime logs
- Recent issues
- Recent events
- Snapshot state
- Configuration state

---

## Logs

Shows panel logs and error reports.

Supported log types:

- General logs
- Error logs
- Tuya logs
- HWiNFO error logs
- Startup profile logs

Logging settings:

```json
{
  "logging": {
    "debug_logging_enabled": true,
    "websocket_logging_enabled": false,
    "tuya_error_logging_enabled": true,
    "hwinfo_error_logging_enabled": true,
    "performance_logging_enabled": false,
    "max_lines": 1500,
    "cleanup_interval_seconds": 900
  }
}
```

---

## Sitemap

Shows the internal route and page structure of the panel.

---

## Reset

Used to restore default settings.

---

# System Monitoring

The panel collects system status from the backend and broadcasts it to the frontend.

Supported public status fields include:

```txt
cpu_percent
ram_percent
ram_used_gb
ram_total_gb
gpu_util
gpu_temp
cpu_temp
cpu_power
gpu_power
uptime
fps
fps_1_low
fps_source
vram_percent
vram_temp
motherboard_temp
vmos_temp
ram_slot_temps
disks_cde
download_speed_mbps
upload_speed_mbps
pc_plug_power_w
total_system_power
estimated_total_system_power
total_system_power_source
```

---

# HWiNFO Integration

HWiNFO is the primary source for sensor data.

Features:

- HWiNFO executable path setting
- HWiNFO worker mode
- HWiNFO snapshot JSON cache
- HWiNFO shared memory / sensor mode preparation
- HWiNFO process detection
- HWiNFO uptime tracking
- HWiNFO automatic restart
- Configurable maximum HWiNFO uptime
- HWiNFO error logging
- FPS data can share the same worker loop
- FPS ignore apps list
- Sensor binding and matching system
- Worker heartbeat tracking
- Worker restart cooldown
- Snapshot age validation

Settings:

```json
{
  "hwinfo": {
    "fps_ignore_apps_text": "",
    "auto_restart_enabled": true,
    "auto_restart_max_uptime_hours": 11,
    "executable_path": ""
  }
}
```

The FPS ignore list is used to exclude false FPS sources such as:

- Desktop Window Manager
- Explorer
- Task Manager
- Panel process
- Python process
- Chrome
- Steam
- Discord
- Spotify
- OBS
- WebView2

---

# Media Control

The panel works with Windows media sessions and system audio APIs.

Features:

- Read active media title
- Read artist information
- Show album art
- Detect media source application
- Play/pause
- Previous track
- Next track
- Seekbar
- Media position
- Media duration
- Volume up
- Volume down
- Direct volume set
- Mute toggle
- Remote volume sync delay
- Remote mute sync delay
- Idle media text
- Custom no-media placeholder

Settings:

```json
{
  "frontend": {
    "seekbar_update_interval_ms": 250,
    "media_refresh_interval_ms": 500,
    "volume_refresh_interval_ms": 250,
    "mute_refresh_interval_ms": 250,
    "media_progress_interval_playing_ms": 150,
    "media_progress_interval_paused_ms": 500,
    "volume_remote_sync_delay_ms": 220,
    "mute_remote_sync_delay_ms": 1200,
    "idle_text": "nihil infinitum est | el. psy. congroo",
    "no_media_placeholder_title": "el. psy. congroo.",
    "hide_seekbar_when_idle": true,
    "show_media_progress_when_idle": false
  }
}
```

---

# Lyrics

The panel can display lyrics for the currently playing track.

Features:

- Lyrics refresh interval
- Lyrics animation interval
- Lyric offset
- Waiting text
- Refresh lyrics when active media changes
- Keep lyrics card idle when no media is active
- Toggle lyrics card visibility
- Lyrics cache behavior
- Synced lyrics support
- Plain lyrics fallback

Settings:

```json
{
  "frontend": {
    "lyrics_refresh_interval_ms": 1000,
    "lyrics_animation_interval_ms": 150,
    "lyric_offset_sec": 0.8,
    "lyrics_waiting_text": "Waiting for lyrics...",
    "show_lyrics_card": true
  }
}
```

---

# Tuya Integration

The panel can control Tuya-compatible smart devices.

Features:

- Local mode
- Cloud mode
- Device status query
- Device on/off toggle
- Brightness control
- Visible device list
- Device ordering
- PC plug key
- PC plug wattage tracking
- Tuya cache
- Tuya connection pool reset
- Tuya check
- Tuya log clearing
- Parallel status workers
- Status batch size
- Per-device error display
- Local command timeout
- Cloud command timeout
- Device timeout
- Retry count

Settings:

```json
{
  "tuya": {
    "visible_device_keys": [],
    "pc_plug_key": "",
    "brightness_popup_timeout_ms": 1600,
    "read_mode": "local",
    "device_timeout_ms": 2500,
    "local_command_timeout_ms": 2500,
    "cloud_command_timeout_ms": 8000,
    "max_parallel_status_workers": 4,
    "status_batch_size": 8
  },
  "api": {
    "tuya": {
      "base_url": "https://openapi.tuyaeu.com",
      "access_id": "",
      "access_secret": ""
    }
  }
}
```

---

# SmartThings Climate Control

The panel provides a SmartThings API-based climate control popup.

Features:

- Climate status query
- Climate temperature level display
- Temperature level update
- Climate power on
- Climate power off
- API level debug info
- API switch debug info
- OAuth callback endpoint
- OAuth access token field
- OAuth refresh token field
- OAuth token expiry field
- SmartThings location ID
- SmartThings device ID

Settings:

```json
{
  "api": {
    "smartthings": {
      "api_key": "",
      "base_url": "https://api.smartthings.com/v1",
      "location_id": "",
      "device_id": "",
      "oauth_client_id": "",
      "oauth_client_secret": "",
      "oauth_refresh_token": "",
      "oauth_access_token": "",
      "oauth_access_token_expires_at": 0,
      "oauth_redirect_uri": ""
    }
  }
}
```

---

# Weather

The panel displays weather information through Open-Meteo.

Features:

- Forecast URL
- Geocoding URL
- Location query
- Location label
- Latitude
- Longitude
- Timezone
- Language setting
- Current temperature
- Feels-like temperature
- Humidity
- Pressure
- Wind speed
- Wind direction
- Daily minimum temperature
- Daily maximum temperature
- Weather summary
- Rain information
- Weather error field
- Configurable refresh interval

Settings:

```json
{
  "api": {
    "meteo": {
      "forecast_url": "https://api.open-meteo.com/v1/forecast",
      "geocoding_url": "https://geocoding-api.open-meteo.com/v1/search",
      "location_query": "Kayseri",
      "location_label": "Kayseri",
      "latitude": 38.7205,
      "longitude": 35.4826,
      "timezone": "Europe/Istanbul",
      "language": "en"
    }
  },
  "performance": {
    "weather_refresh_interval_minutes": 30
  }
}
```

---

# Shift System

The panel can read shift data from an Excel/SharePoint workbook.

Features:

- Shared Excel URL
- Sheet name selection
- Employee name selection
- Name column selection
- Date row selection
- Shift cache file
- Shift cache metadata file
- Tomorrow shift text
- Tomorrow shift subtitle
- Shift refresh endpoint
- Configurable cache check interval
- Custom liquid fill animation for the shift card

Settings:

```json
{
  "api": {
    "shift": {
      "share_url": "",
      "sheet_name": "Shift",
      "employee_name": "",
      "name_column": 3,
      "date_row": 2
    }
  },
  "performance": {
    "shift_cache_check_interval_minutes": 30
  }
}
```

---

# Panel Buttons

The panel includes customizable shortcut buttons.

Each button supports:

```json
{
  "id": "button_id",
  "label": "Button Label",
  "visible": true,
  "variant": "white-glow",
  "command": "/command",
  "secondary_command": "",
  "method": "GET",
  "confirm_text": "",
  "icon_svg": "<svg></svg>"
}
```

Supported method values:

```txt
GET
POST
SPECIAL
```

Common button actions:

- Open Admin CMD
- Run DNS redirect command
- Open climate popup
- Open Task Manager
- Start YouTube Shorts window
- Kill YouTube Shorts window
- Start Spotify window
- Kill Spotify window
- Sleep PC
- Restart PC
- Shutdown PC
- Run custom commands

Button features:

- Show or hide button
- Change label
- Change icon
- Change command
- Change secondary command
- Change method
- Add confirmation text
- Change visual style variant

---

# External Windows

The panel can open separate WebView windows.

---

## YouTube Shorts Window

Features:

- YouTube Shorts URL setting
- Separate frameless WebView window
- Selected monitor targeting
- Always-on-top behavior
- Window title setting
- Kill window endpoint
- Custom CSS/JS adjustments for Shorts
- WebView2 stability arguments
- Fullscreen video styling
- Scrollbar hiding

Settings:

```json
{
  "external_windows": {
    "youtube": {
      "url": "https://www.youtube.com/shorts/",
      "window_title": "YouTube Ekrani",
      "target_monitor_device": ""
    }
  }
}
```

---

## Spotify Window

Features:

- Spotify URL setting
- Separate frameless WebView window
- Selected monitor targeting
- Always-on-top behavior
- Window title setting
- Kill window endpoint
- WebView2 window positioning
- Frameless display mode

Settings:

```json
{
  "external_windows": {
    "spotify": {
      "url": "https://open.spotify.com/intl-tr/",
      "window_title": "Spotify Ekrani",
      "target_monitor_device": ""
    }
  }
}
```

---

# Visual System

The panel is built around a 1920x1080 base layout and scales to the active window.

Visual features:

- Custom background image
- Geforcea font support
- Grid-based layout
- Top system cards
- Bottom control cards
- Liquid SVG animations
- Per-card liquid themes
- Sketch button animation
- Confirmation popup
- Tuya brightness popup
- Climate level popup
- Volume knob visual
- Responsive scale system
- Landscape layout
- Vertical `/dikey` route support
- Card visibility toggles
- Idle animation behavior
- Low performance mode

Frontend visibility settings:

```json
{
  "frontend": {
    "panel_language": "en",
    "show_fps_card": true,
    "show_date_weather_block": true,
    "show_tuya_card": true,
    "show_now_playing_card": true,
    "show_lyrics_card": true
  }
}
```

Liquid animation settings:

```json
{
  "frontend": {
    "liquid_animation_enabled": true,
    "liquid_animation_fps": 16,
    "liquid_animation_mode": "light",
    "liquid_wave_when_idle": false,
    "liquid_theme_cpu": "default_glass",
    "liquid_theme_gpu": "default_glass",
    "liquid_theme_ram": "default_glass",
    "liquid_theme_fps": "default_glass",
    "liquid_theme_power": "default_glass",
    "liquid_theme_shift": "default_glass",
    "animation_level": "normal",
    "low_performance_mode": false
  }
}
```

---

# Health, Logs, and Sitemap

## Health

The health report summarizes the internal status of the panel.

It may include:

- Overall status
- Snapshot information
- Configuration state
- Checks
- Issues
- Recent events
- HWiNFO worker status
- HWiNFO app status
- Tuya status
- Weather status
- SmartThings status
- Media status
- WebSocket status
- Runtime log status

---

## Logs

The logging system supports:

- General log
- Error log
- Tuya log
- HWiNFO error log
- Startup profile log
- Maximum line limit
- Cleanup interval
- Log clear endpoint
- Tuya-only log clear endpoint

Logging settings:

```json
{
  "logging": {
    "debug_logging_enabled": true,
    "websocket_logging_enabled": false,
    "tuya_error_logging_enabled": true,
    "hwinfo_error_logging_enabled": true,
    "performance_logging_enabled": false,
    "max_lines": 1500,
    "cleanup_interval_seconds": 900
  }
}
```

---

## Sitemap

The sitemap page shows the internal route and page structure of the panel.

---

# API Endpoints

## Pages

```txt
GET  /
GET  /dikey
GET  /settings
GET  /hata
GET  /sitemap
```

## Static Files

```txt
GET  /script.js
GET  /liquid_themes.js
GET  /settings_i18n.js
GET  /settings_i18n_tr.js
GET  /settings_i18n_en.js
GET  /settings-theme-light.css
GET  /settings-theme-dark.css
GET  /resimler/{path}
GET  /fonts/{path}
```

## Status / Health

```txt
GET  /status
GET  /ws/status
GET  /health
GET  /api/health/report
GET  /hata/data
GET  /sitemap/data
```

## Settings

```txt
GET   /api/settings
POST  /api/settings
POST  /api/settings/reset
GET   /api/monitors
```

## Weather

```txt
GET  /weather/meteo
GET  /weather/mgm
```

## Logs

```txt
POST  /api/logs/clear
POST  /api/tuya/logs/clear
```

## HWiNFO

```txt
POST  /api/hwinfo/restart
```

## Shift

```txt
POST  /api/shift/refresh
```

## Media

```txt
GET  /media/seek
GET  /setvolume
GET  /mute
```

## Tuya

```txt
GET   /tuya/status
GET   /tuya/pc_debug
GET   /tuya/toggle/{device_key}
GET   /tuya/brightness/{device_key}
POST  /api/tuya/check
POST  /api/tuya/reset
```

## SmartThings

```txt
GET   /callback
GET   /smartthings/oauth/callback
GET   /smartthings/climate/status
POST  /smartthings/climate/level
POST  /smartthings/climate/power
```

## Commands

```txt
GET   /admincmd
GET   /taskmgr
GET   /sleep
GET   /restart
GET   /shutdown
GET   /spotify
GET   /shorts
GET   /kill/spotify
GET   /kill/shorts
GET   /dnsredir
POST  /dnsredir
```

---

# Requirements

## Operating System

- Windows 10
- Windows 11

The panel is Windows-focused because it uses:

- Windows APIs
- WebView windows
- COM audio endpoint control
- HWiNFO integration
- Windows media commands
- Windows monitor/window positioning

## Python

Recommended:

```txt
Python 3.10+
```

## Python Packages

Required or recommended packages:

```txt
aiohttp
psutil
pywebview
tinytuya
requests
openpyxl
```

Install them with:

```bash
pip install aiohttp psutil pywebview tinytuya requests openpyxl
```

## External Requirements

For full functionality:

- HWiNFO64
- Microsoft Edge WebView2 Runtime
- Tuya-compatible smart devices
- Tuya local key or Tuya Cloud API credentials
- SmartThings account and device information
- Internet connection
- Open-Meteo access
- Excel/SharePoint shift link
- Spotify account/session if using Spotify WebView
- YouTube access if using YouTube Shorts WebView

---

# Installation

1. Clone or download the repository.

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

2. Install Python packages.

```bash
pip install aiohttp psutil pywebview tinytuya requests openpyxl
```

3. Install HWiNFO64.

4. Set the HWiNFO executable path in `settings.json`.

5. Copy the example settings file.

```bash
copy settings.example.json settings.json
```

6. Edit `settings.json` with your own device/API settings.

7. Start the panel.

```bash
python panel_app.py
```

---

# Running

## Main Panel

```bash
python panel_app.py
```

Default URL:

```txt
http://localhost:5001/
```

Settings page:

```txt
http://localhost:5001/settings
```

## HWiNFO Worker

```bash
python hwinfo_worker.py
```

## Spotify WebView

```bash
python spotify.py
```

## YouTube Shorts WebView

```bash
python youtube.py
```

---

# File Structure

```txt
panel_app.py              Main backend application
main.html                 Main panel UI
script.js                 Frontend logic
settings.html             Settings UI
settings.json             Local user settings
settings_runtime.py       Settings load/save/reset system
hwinfo_worker.py          HWiNFO worker entry point
audio_runtime.py          Windows audio and media command runtime
tuya_runtime.py           Tuya local/cloud runtime
spotify.py                Spotify WebView window
youtube.py                YouTube Shorts WebView window
win_utils.py              Windows monitor/window helpers
app_logging.py            Logging utilities
logs/                     Runtime logs
logs/runtime/             Runtime cache files
webview_cache/            WebView cache
resimler/                 Panel images
fonts/                    Panel fonts
```

---

# Security Notes

Do not commit your real `settings.json` file to a public GitHub repository.

It may contain sensitive information such as:

- Tuya access ID
- Tuya access secret
- SmartThings API key
- SmartThings OAuth client secret
- SmartThings refresh token
- SmartThings access token
- Device IDs
- Location IDs
- Ngrok callback URL
- Personal SharePoint/Excel links
- Monitor device IDs
- Local script paths
- Private command paths

Use a safe public example file instead:

```txt
settings.example.json
```

Keep secret fields empty:

```json
{
  "api": {
    "tuya": {
      "base_url": "https://openapi.tuyaeu.com",
      "access_id": "",
      "access_secret": ""
    },
    "smartthings": {
      "api_key": "",
      "location_id": "",
      "device_id": "",
      "oauth_client_id": "",
      "oauth_client_secret": "",
      "oauth_refresh_token": "",
      "oauth_access_token": "",
      "oauth_redirect_uri": ""
    },
    "shift": {
      "share_url": ""
    }
  }
}
```

Recommended `.gitignore`:

```gitignore
settings.json
devices.json
logs/
webview_cache/
shift_cache.xlsx
shift_cache_meta.json
__pycache__/
*.pyc
```

---

# Notes

This project is not a generic commercial dashboard.  
It is a highly customized personal Windows control panel.

The code is modular:

- `panel_app.py` handles the main backend
- `main.html` handles the main UI
- `script.js` handles frontend behavior
- `settings_runtime.py` handles settings
- `tuya_runtime.py` handles Tuya devices
- `audio_runtime.py` handles Windows audio/media controls
- `youtube.py` and `spotify.py` handle external WebView windows
- `win_utils.py` handles Windows monitor/window utilities

---

# License

This project was built for personal use. Feel free to use personally. For Commercial use contact me
