#!/bin/bash
# Sets the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activates the virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Runs the Python script using the Python executable from the virtual environment
python "$SCRIPT_DIR/main.py"
