#!/usr/bin/env sh
cd "$(dirname "$0")"
python3 -c "import yt_dlp" 2>/dev/null || python3 -m pip install --user --quiet yt-dlp || true
exec python3 server.py "$@"
