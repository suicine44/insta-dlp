#!/bin/bash

# Define the persistent profile directory
# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="$SCRIPT_DIR/chrome_profile"

mkdir -p "$PROFILE_DIR"

echo "[*] Launching Google Chrome with persistent profile..."
echo "    Profile: $PROFILE_DIR"
echo "    URL: https://www.instagram.com/gauchaasmr/"

# Launch Chrome in background
google-chrome \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  https://www.instagram.com/gauchaasmr/ > /dev/null 2>&1 &

echo "[+] Browser launched! perform your login manually."
