#!/usr/bin/env bash
# Developer helper: run Lua in the test game (scripts/testgame.ps1 + RealVehicleInteriors_Dev).
#   dev/lua.sh dev/lua/state.lua [depth]
#   dev/lua.sh -e 'return getPlayer():getX()' [depth]
url="http://127.0.0.1:18470/lua"
if [ "$1" = "-e" ]; then
    curl -s -m 70 -X POST --data-binary "$2" "$url?depth=${3:-3}"
else
    curl -s -m 70 -X POST --data-binary @"$1" "$url?depth=${2:-3}"
fi
echo
