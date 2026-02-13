#!/bin/bash
set -e

echo "[*] Updating package lists..."
sudo apt-get update

echo "[*] Installing dependencies..."
sudo apt-get install -y wget

echo "[*] Downloading Google Chrome..."
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

echo "[*] Installing Google Chrome..."
# Handling potential dependency errors with apt-get install -f
sudo dpkg -i google-chrome-stable_current_amd64.deb || sudo apt-get install -f -y

echo "[*] Cleaning up..."
rm google-chrome-stable_current_amd64.deb

echo "[+] Google Chrome installed successfully!"
google-chrome --version
