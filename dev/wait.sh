#!/usr/bin/env bash
# Developer helper: wait for the test game to reach the main menu or the world.
#   dev/wait.sh menu | dev/wait.sh ingame
here="$(cd "$(dirname "$0")" && pwd)"
console="$here/../build/rv/testhome/Zomboid/console.txt"
case "$1" in
    menu) check='return MainScreen and MainScreen.instance and MainScreen.instance:isVisible() and "READY" or "wait"' ;;
    ingame) check='local p = getPlayer(); return p and p:getCurrentSquare() and MainScreen.instance and not MainScreen.instance:isVisible() and "READY" or "wait"' ;;
    *) echo "usage: wait.sh menu|ingame"; exit 2 ;;
esac
for i in $(seq 1 90); do
    r=$(curl -s -m 20 -X POST --data-binary "$check" http://127.0.0.1:18470/lua 2>/dev/null)
    if echo "$r" | grep -q READY; then echo "$1 reached after ~$((i * 4))s"; exit 0; fi
    if [ -f "$console" ] && grep -q "GameThread exited" "$console"; then
        echo "GAME EXITED"; grep -n "uncaughtException" -A 12 "$console" | head -30; exit 1
    fi
    sleep 4
done
echo "timeout waiting for $1"; exit 1
