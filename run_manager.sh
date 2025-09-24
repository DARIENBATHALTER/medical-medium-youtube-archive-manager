#!/bin/bash
# Medical Medium YouTube Archive Manager Startup Script
# Usage: ./run_manager.sh [options]

cd /home/mm
source youtube_archive_env/bin/activate
python youtube_archive_manager.py "$@"