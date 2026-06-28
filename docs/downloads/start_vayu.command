#!/bin/bash
# VAYU - macOS Launcher

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "   VAYU - AI Assistant"
echo "========================================"
echo ""

echo "[1/3] Installing/updating dependencies..."
python3 -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "[!] pip install failed. Make sure Python 3.10+ is installed."
    echo "    Download from: https://python.org"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[2/3] Setting up Playwright browsers..."
python3 -m playwright install chromium 2>/dev/null

echo "[3/3] Launching VAYU..."
echo ""
python3 main.py

echo ""
echo "VAYU has exited."
read -p "Press Enter to close..."
