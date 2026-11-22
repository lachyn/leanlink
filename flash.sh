#!/bin/sh
# Cross-platform OTA flasher for LeanLink (wireless Android Auto / CarPlay adapters, projects ly6071 / ly5140).
#
# Works with any POSIX shell + curl:
#   - Linux / macOS terminal
#   - Android: `adb shell` (toybox curl in /system/bin) or Termux (`pkg install curl`)
#
# Usage: sh flash.sh [options] <update.img>
#   -i IP       box address (default: auto-detect 192.168.1.101, 192.168.43.1)
#   -I IFACE    bind curl to a network interface (Android: wlan0, so traffic does not leave via mobile data)
#   -c CHANNEL  Wi-Fi channel to set after flashing (default 36; 0 = leave unchanged, no reboot)
#   -r          factory reset after flashing (wipes paired Bluetooth phones; recommended when upgrading from stock)
#   -f          skip the image-name vs. model check (only if you know what you are doing)
#
# The box must be powered (plugged into a car / PC USB port) and this device must be joined to its
# Wi-Fi: LeanLink-xxxx once LeanLink is installed, CAR2-xxxx on the stock firmware (password 88888888,
# some stock units 12345678).

set -u

IP=""
IFACE=""
CHANNEL=36
RESET=0
FORCE=0

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

while getopts "i:I:c:rfh" opt; do
    case "$opt" in
        i) IP=$OPTARG ;;
        I) IFACE=$OPTARG ;;
        c) CHANNEL=$OPTARG ;;
        r) RESET=1 ;;
        f) FORCE=1 ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage
IMG=$1
[ -f "$IMG" ] || die "image not found: $IMG"
command -v curl >/dev/null 2>&1 || die "curl is required"

CURL="curl -sS"
[ -n "$IFACE" ] && CURL="$CURL --interface $IFACE"

host_json() { $CURL --max-time "${2:-4}" "http://$1/cgi-bin/index.cgi?id=host" 2>/dev/null; }
json_field() { sed -n "s/.*\"$1\" *: *\"\{0,1\}\([^\",}]*\).*/\1/p" | head -n 1; }

# 1. Find the box
if [ -z "$IP" ]; then
    for cand in 192.168.1.101 192.168.43.1; do
        if host_json "$cand" 3 | grep -q appver; then IP=$cand; break; fi
    done
fi
[ -n "$IP" ] || die "box not reachable. Join its Wi-Fi (LeanLink-xxxx or CAR2-xxxx) first; on a phone also disable mobile data or use -I wlan0."
HOST=$(host_json "$IP") || die "no answer from $IP"
APPVER=$(printf '%s' "$HOST" | json_field appver)
UPDATE=$(printf '%s' "$HOST" | json_field update)
NAME=$(printf '%s' "$HOST" | json_field name)
MODEL=$(printf '%s' "$APPVER" | cut -d. -f2)
log "Found box '$NAME' at $IP, firmware $APPVER (project ly$MODEL), updater state $UPDATE"

# 2. Model check (images are NOT interchangeable between ly6071 and ly5140)
case "$MODEL" in
    6071|5140) ;;
    *) [ "$FORCE" = 1 ] || die "unsupported project ly$MODEL - this firmware only exists for ly6071 and ly5140" ;;
esac
if [ "$FORCE" = 0 ]; then
    base=$(basename "$IMG")
    case "$base" in
        *5140*) imgmodel=5140 ;;
        *6071*|update_aa_fixed*) imgmodel=6071 ;;
        *) die "cannot tell the model from file name '$base' (expect *5140* or update_aa_fixed*); use -f to override" ;;
    esac
    [ "$imgmodel" = "$MODEL" ] || die "image '$base' is for ly$imgmodel but the box is ly$MODEL - refusing"
fi
[ "$UPDATE" = 0 ] || die "updater is busy (update=$UPDATE); power-cycle the box and retry"

# 3. Upload
log "Uploading $IMG ..."
RESP=$($CURL --max-time 180 -F "file=@$IMG;filename=blob;type=application/octet-stream" \
    "http://$IP/cgi-bin/index.cgi?id=upload") || die "upload failed (curl error)"
printf '%s\n' "$RESP"
printf '%s' "$RESP" | grep -q '"code": *0' || die "box rejected the image"

# 4. Wait for the flash write (LED blinks; do NOT unplug)
log "Image accepted - writing to flash (~75 s). Do NOT unplug the box."
i=0
while :; do
    sleep 5
    i=$((i + 5))
    st=$(host_json "$IP" | json_field update)
    log "  updater state: ${st:-?} (${i}s)"
    [ "$st" = 3 ] && break
    case "$st" in 4|5|6|7|8|9) die "update failed with state $st" ;; esac
    [ $i -ge 600 ] && die "timeout waiting for update to finish"
done
log "Flash write complete."

# 5. Optional factory reset (clears stale Bluetooth pairings that break reconnects)
if [ "$RESET" = 1 ]; then
    log "Factory reset (rst=1) - box reboots ..."
    $CURL --max-time 5 "http://$IP/cgi-bin/index.cgi?id=set&rst=1" >/dev/null 2>&1
    log "Waiting for the box to come back (re-join its Wi-Fi if your device does not reconnect automatically) ..."
    i=0
    sleep 15
    until host_json "$IP" 3 | grep -q appver; do
        sleep 3; i=$((i + 3))
        [ $i -ge 180 ] && die "box did not come back after reset; channel not set"
    done
fi

# 6. Wi-Fi channel, then make sure the box restarts into the new firmware.
# LeanLink restarts by itself ~10 s after the write; the stock firmware stays in "update done" state
# (update=3, LED solid white) until restarted, and id=set&wifi=N only restarts when the channel changes.
# So wait for the box to come back with update=0 and send an explicit restart (conn=aoa) only if it is
# still in state 3 after 25 s.
if [ "$CHANNEL" != 0 ]; then
    log "Setting Wi-Fi channel $CHANNEL ..."
    $CURL --max-time 5 "http://$IP/cgi-bin/index.cgi?id=set&wifi=$CHANNEL" >/dev/null 2>&1
fi
log "Waiting for the box to restart into the new firmware ..."
# Phones that reached the box through Android Auto drop its Wi-Fi when the AA service stops for the update,
# and every phone loses it while the box restarts; keep trying while the user rejoins.
i=0
sent=0
while :; do
    sleep 3
    i=$((i + 3))
    st=$(host_json "$IP" 3 | json_field update)
    [ "$st" = 0 ] && break
    if [ "$st" = 3 ] && [ $i -ge 25 ] && [ "$sent" = 0 ]; then
        log "Box did not restart by itself - sending a restart request."
        $CURL --max-time 5 "http://$IP/cgi-bin/index.cgi?id=set&conn=aoa" >/dev/null 2>&1
        sent=1
    fi
    [ -z "$st" ] && [ $i -eq 30 ] && log "Box not reachable - rejoin its Wi-Fi (LeanLink-xxxx or CAR2-xxxx) if your device does not do it by itself."
    [ $i -ge 300 ] && die "box did not come back; unplug and replug it (the update is already written)"
done
NEW=$(host_json "$IP" | json_field appver)
log "Done. Box now runs firmware ${NEW:-?} (was $APPVER)."
