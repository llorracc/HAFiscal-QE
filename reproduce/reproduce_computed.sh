#!/bin/bash

# Make sure the necessary requirements are available
source ./reproduce/reproduce_environment.sh

# Change directory to the location of the Python script
cd Code/HA-Models || exit

# Create empty version file for full reproduction
rm -f version
touch version

# Pass HAFISCAL_RUN_STEP_3 environment variable if set
# (defaults to false in do_all.py if not set)
export HAFISCAL_RUN_STEP_3="${HAFISCAL_RUN_STEP_3:-false}"

# Run the Python script
python do_all.py
