#!/bin/bash

echo "🎓 Starting workspace…"

### BEGIN BACKUP ###
PROJECT_ROOT="/Users/adrian/Documents/PROJECTS/PRISM/Ressources/🕹StaffHero"
ABLETON_SET="$PROJECT_ROOT/live/StaffHero Project/StaffHero.als"
### BEGIN BACKUP ###

SIBELIUS_SCORE="$PROJECT_ROOT/sibelius/StaffHero.sib"
README_MD="$PROJECT_ROOT/README.md"
START_SCRIPT="$PROJECT_ROOT/start/start_mac.sh"
MAX_PATCH="$PROJECT_ROOT/viewer/verovio4live/verovio4live/verovio4live.maxproj"

TRELLO_CARD="https://trello.com/c/1duG7BjH/64-%F0%9F%95%B9-staffwars"
GDRIVE_FOLDER="https://drive.google.com/drive/folders/1Q7BcmFBfPEIpm82cShTVhhbKj8Rxzetv"

GITHUB_ROOT="https://github.com/AdrianArtacho/"
GITHUB_REPO="$GITHUB_ROOT/staffhero"

# ==============================
# Launch applications
# ==============================

# open "$ABLETON_SET"
# sleep 2

# open "$SIBELIUS_SCORE"
# sleep 2

# open "$MAX_PATCH"
# sleep 2

# ==============================
# Project context
# ==============================

# open "$README_MD"
# sleep 2

# open "$PROJECT_ROOT"
# sleep 2

# open "$START_SCRIPT"
# sleep 2

# ==============================
# Online resources
# ==============================

# open "$TRELLO_CARD"
# sleep 2

# open "$GDRIVE_FOLDER"
# sleep 2

# open "$GITHUB_REPO"
# sleep 2

# ==============================
# Local server
# ==============================

# echo "🌐 Starting local server on port 8000…"
# cd "$PROJECT_ROOT" || exit
# python3 -m http.server 8000 &
# sleep 2
# open "http://localhost:8000"

# ==============================
# SourceTree
# ==============================

open -a SourceTree "$PROJECT_ROOT"
sleep 2

echo "✅ Workspace ready."

# ==============================
# Start StaffHero game
# ==============================

echo "🎮 Starting StaffHero..."

cd "$PROJECT_ROOT" || exit

# activate virtual environment
source .venv/bin/activate

# run the game
python staffwars_like.py &