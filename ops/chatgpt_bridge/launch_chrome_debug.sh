#!/usr/bin/env bash
# Retired GUI launcher.  The canonical control plane is state-root bound.

LEGACY_GUI_BRIDGE_DISABLED=1
export LEGACY_GUI_BRIDGE_DISABLED
echo "legacy GUI launcher is disabled; use ops/control_plane_watchdog.py" >&2
exit 2
