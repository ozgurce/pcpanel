L-Connect direct control

Active path:
- lconnect_control.py sends Quick Sync merge commands to L-Connect Service at 127.0.0.1:11021.
- lconnect_profiles.json keeps the compact lighting profile used by the panel.
- last_lconnect_state.json is created at runtime before "off" and is used by "on" to restore the user's last L-Connect effect.
- No PowerShell, admin prompt, service restart, or file copy is used in the active path.

Panel commands:
- on  -> python lconnect_control.py on --profile lconnect_profiles.json --state-cache last_lconnect_state.json
- off -> python lconnect_control.py off --profile lconnect_profiles.json --state-cache last_lconnect_state.json

Panel settings:
- L-Connect profile, effect cache, data folder, merge state file, service URL, and timeout are configurable from Settings > API & Commands > Command Paths.

Long-method restore point:
- If the user says "uzun yonteme don", restore from:
  D:\Program\pc-control-backups\pc-control-panel-long-method-20260507-170432
