#!/bin/bash
cd "$(dirname "$0")"
uv run python -m helper
echo "Setup complete!"
