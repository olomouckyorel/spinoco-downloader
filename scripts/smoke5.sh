#!/bin/bash
# scripts/smoke5.sh - Thin wrapper pro tools/smoke5.py

set -e

# Přejdi do kořenového adresáře projektu
cd "$(dirname "$0")/.."

# Spusť smoke test
python tools/smoke5.py "$@"
