#!/bin/bash
cd "$(dirname "$0")"
python3 -m helper
python3 misc/convert.py