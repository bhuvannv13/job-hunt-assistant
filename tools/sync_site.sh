#!/usr/bin/env sh
# Copy the Python modules the website runs in the browser.
set -e
cd "$(dirname "$0")/.."
mkdir -p docs/py/jobhunt
for f in __init__ models skills match cv tracker tailor; do cp "jobhunt/$f.py" "docs/py/jobhunt/$f.py"; done
