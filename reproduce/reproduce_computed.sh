#!/bin/bash

# Make sure the necessary requirements are available
source ./reproduce/reproduce_environment.sh

# Change directory to the location of the Python script
cd Code/HA-Models || exit

# Create empty version file for full reproduction
rm -f version
touch version

# Run the Python script
python do_all.py
