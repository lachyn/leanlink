#!/bin/sh
# Run a shell command on a LeanLink box running a DEBUG image (HTTP shell on :8080, root, no password).
#
# Usage: tools/box_shell.sh [-d] 'free; ps w'
#   -d   talk to the box directly from this computer (it must be joined to the box Wi-Fi);
#        default: through an Android phone over adb (phone joined to the box Wi-Fi), handy when this
#        computer has no 5 GHz Wi-Fi. Same as LEANLINK_DIRECT=1.
# Environment: LEANLINK_IP (default 192.168.1.101), LEANLINK_SHELL_LOG (default ./leanlink-shell.log): every
# command and its output is appended there, so another terminal can follow it with `tail -f`.
# Avoid `find /sys` or reading arbitrary sysfs files: some hang the kernel and the watchdog reboots the box.
# --- env ---
DIRECT=${LEANLINK_DIRECT:-0}
IP=${LEANLINK_IP:-192.168.1.101}
LOG=${LEANLINK_SHELL_LOG:-./leanlink-shell.log}
# --- end env ---

while getopts "dh" opt; do
    case "$opt" in
        d) DIRECT=1 ;;
        *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
    esac
done
shift $((OPTIND - 1))
[ $# -ge 1 ] || { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
CMD="$*"
URL="http://$IP:8080/cgi-bin/sh.cgi"

{ printf '\n\033[1;36m### %s  $ %s\033[0m\n' "$(date +%H:%M:%S)" "$CMD"; } | tee -a "$LOG"
if [ "$DIRECT" = 1 ]; then
    curl -sS --max-time 30 --data-binary "$CMD" "$URL"
else
    printf '%s' "$CMD" | adb shell "curl -sS --max-time 30 --interface wlan0 --data-binary @- $URL"
fi 2>&1 | tee -a "$LOG"
