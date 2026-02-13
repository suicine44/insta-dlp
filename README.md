## insta-dlp wrapper script
Usage: ./insta-dlp <username> [options]

## Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

## Run python script with forwarded arguments
python3 "$SCRIPT_DIR/main.py" "$@"
