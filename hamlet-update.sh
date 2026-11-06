#!/bin/sh
# Hamlet apps – install / update from a zip uploaded to Home Assistant.
#
# Usage (Terminal & SSH add-on):   sh /config/hamlet-update.sh
#   options:  --no-restart     install but don't restart Home Assistant
#             path/to/file.zip use that zip instead of the newest hamlet-*.zip
#
# Installs every Hamlet integration in the zip (Hamlet Home, Hamlet Geyser, …).
# Settings, schedules and history live in .storage and are NOT touched.
set -eu

if [ -n "${HAMLET_CONFIG_DIR:-}" ]; then
  CONFIG="$HAMLET_CONFIG_DIR"
elif [ -f /config/configuration.yaml ]; then
  CONFIG=/config
elif [ -f /homeassistant/configuration.yaml ]; then
  CONFIG=/homeassistant
else
  echo "✗ Can't find the Home Assistant config folder (/config or /homeassistant)."; exit 1
fi
BACKUP_ROOT="$CONFIG/hamlet_backup"
TMP="${TMPDIR:-/tmp}/hamlet_update.$$"
RESTART=1
ZIP=""
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    *) ZIP="$arg" ;;
  esac
done

say() { printf '%s\n' "$*"; }
fail() { say "✗ $*"; rm -rf "$TMP"; exit 1; }
field() { sed -n "s/.*\"$2\"[^\"]*\"\\([^\"]*\\)\".*/\\1/p" "$1/manifest.json" 2>/dev/null | head -n 1; }

# 1. find the zip: newest hamlet-*.zip in the config folder, then subfolders, /share, /media
if [ -z "$ZIP" ]; then
  ZIP=$(ls -t "$CONFIG"/hamlet-*.zip 2>/dev/null | head -n 1 || true)
fi
if [ -z "$ZIP" ]; then
  ZIP=$(find "$CONFIG" /share /media -maxdepth 4 -type f -iname 'hamlet-*.zip' \
          -not -path '*/hamlet_backup/*' -not -path '*/hamlet_geyser_backup/*' -exec ls -t {} + 2>/dev/null | head -n 1 || true)
fi
[ -n "$ZIP" ] && [ -f "$ZIP" ] || fail "No hamlet zip found in $CONFIG (or its subfolders, /share, /media). Upload the zip first."
say "→ Using $(basename "$ZIP")"

# 2. extract
rm -rf "$TMP"; mkdir -p "$TMP"
if command -v unzip >/dev/null 2>&1; then
  unzip -oq "$ZIP" -d "$TMP" || fail "Could not unzip $ZIP"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m zipfile -e "$ZIP" "$TMP" || fail "Could not unzip $ZIP"
else
  fail "Neither unzip nor python3 is available in this terminal."
fi

MANIFESTS=$(find "$TMP" -type f -name manifest.json -path '*custom_components/hamlet_*' | sort)
[ -n "$MANIFESTS" ] || fail "The zip doesn't contain any Hamlet app – is it the right file?"

# 3. install each app, backing up the current version
mkdir -p "$CONFIG/custom_components" "$BACKUP_ROOT"
NEW_APPS=""
for manifest in $MANIFESTS; do
  SRC=$(dirname "$manifest")
  DOMAIN=$(basename "$SRC")
  case "$DOMAIN" in hamlet_*) ;; *) continue ;; esac
  TARGET="$CONFIG/custom_components/$DOMAIN"
  NAME=$(field "$SRC" name); NEW=$(field "$SRC" version); OLD=$(field "$TARGET" version)
  if [ -d "$TARGET" ]; then
    rm -rf "$BACKUP_ROOT/$DOMAIN"; cp -r "$TARGET" "$BACKUP_ROOT/$DOMAIN"
  fi
  rm -rf "$TARGET.new"; cp -r "$SRC" "$TARGET.new"; rm -rf "$TARGET"; mv "$TARGET.new" "$TARGET"
  find "$TARGET" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  if [ -n "$OLD" ]; then
    say "✓ ${NAME:-$DOMAIN} updated $OLD → $NEW"
  else
    say "✓ ${NAME:-$DOMAIN} $NEW installed"
    NEW_APPS="$NEW_APPS ${NAME:-$DOMAIN},"
  fi
done
# old single-app backup folder from earlier versions
rm -rf "$CONFIG/hamlet_geyser_backup" 2>/dev/null || true

SCRIPT=$(find "$TMP" -type f -name hamlet-update.sh | head -n 1)
[ -n "$SCRIPT" ] && cp "$SCRIPT" "$CONFIG/hamlet-update.sh"
rm -rf "$TMP"
rm -f "$ZIP"
say "  Previous versions kept in hamlet_backup. Settings and history are kept."

# 4. restart
if [ "$RESTART" -eq 1 ]; then
  if command -v ha >/dev/null 2>&1; then
    say "→ Restarting Home Assistant… refresh the browser (Ctrl+F5) in about a minute."
    ha core restart || say "! Restart failed – restart from Settings → System instead."
  else
    say "! Restart Home Assistant from Settings → System to load the new version."
  fi
else
  say "  Restart Home Assistant to load the new version."
fi
if [ -n "$NEW_APPS" ]; then
  say "  New:${NEW_APPS%,} – add it in Settings → Devices & services → Add integration."
fi
