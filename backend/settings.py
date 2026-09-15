"""Paths and binary locations, overridable via environment variables.

Why this exists: the same code runs on a dev machine (no Xray binary, no
template) and on the real server (different paths, Xray installed).
Environment variables let the operator adapt without editing code, and the
defaults work out of the box when the panel runs from the repo root.

- LESSERV_TEMPLATE_PATH: the user-provided semi-complete Xray config the
  panel fills. Missing on a fresh install — sync() then only warns.
- LESSERV_XRAY_CONFIG_PATH: the filled config the panel writes and hands
  to the Xray subprocess.
- LESSERV_XRAY_BINARY: the executable name (PATH lookup) or absolute path
  of Xray. Absent on dev machines — the subprocess is then skipped.
- LESSERV_SERVER_ADDRESS: public domain/IP placed in share links. Empty on
  a fresh install — the links endpoint then answers 409 until it is set.
"""

import os

TEMPLATE_PATH = os.environ.get(
    "LESSERV_TEMPLATE_PATH", "config/xray_template.json"
)
XRAY_CONFIG_PATH = os.environ.get(
    "LESSERV_XRAY_CONFIG_PATH", "data/xray_config.json"
)
XRAY_BINARY = os.environ.get("LESSERV_XRAY_BINARY", "xray")
SERVER_ADDRESS = os.environ.get("LESSERV_SERVER_ADDRESS", "")
