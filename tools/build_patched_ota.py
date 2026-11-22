#!/usr/bin/env python3
"""Build the LeanLink firmware (patched vendor OTA) for ly6071 and ly5140 adapters.

Input is the vendor's own stock OTA (update.img) for the model; it is not part of this repository
(see docs/BUILDING.md). The builder

1. decrypts the OTA, verifies the MD5 envelope, the CPIO checksums and sw-description;
2. unpacks the `customer` SquashFS and replaces:
   - app/lyLink.sh, app/lyLoadModule.sh, app/blink.sh: start scripts with the fixes
     (USB re-bind watchdog, /tmp/udhcpd.conf, no HiCar P2P / fake BLE identity, Android Auto default
     after a reset, channel 36 default, CarPlay -> Android Auto switch, LeanLink-xxxx name);
   - app/otto_goc: stub (Ottopilot BLE daemon disabled);
   - app/system.json: LeanLink version string (ends with ".LL", ".LL-debug" for --debug) and LED pin;
   - ota/www/index.html + js/cpbox.js: web UI patched in place (LeanLink look, verified local upload,
     link to the newest release, settings with explanations, private problem report);
   - app/logo/*.png: LeanLink splash screens from tools/branding/png/;
3. rebuilds the SquashFS with the original block size, timestamp, inode count and size limit;
4. re-packs the CPIO archive, wraps and encrypts it, then decrypts the written file again and compares.

--debug (research only) additionally starts a root shell over HTTP on port 8080 without any password. Anyone on
the box Wi-Fi gets root, so never give such an image to others (see docs/BUILDING.md, "Research and debugging").

Everything the firmware changes is in this file (scripts inline), in tools/webui/ and in
tools/branding/png/. The vendor's binaries, kernel and bootloader are untouched.

This file is generated from the LeanLink development repository; keep changes in sync there.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leanlink_ota as lo

BASE = Path(__file__).resolve().parent.parent
SPLASH_DIR = Path(__file__).resolve().parent / "branding" / "png"
CUSTOMER_SIZE_LIMIT = 0x3A0000  # size of the customer partition (3,801,088 bytes)


@dataclasses.dataclass(frozen=True)
class ModelProfile:
    model_id: str
    ly_project: str
    radio_desc: str
    crypto_flag: str
    testcp_flag: str
    led_cfg: str
    patched_appver: str
    stock_relpath: str
    out_relpath: str


PROFILES: dict[str, ModelProfile] = {
    "6071": ModelProfile(
        model_id="6071",
        ly_project="ly6071",
        radio_desc="Allwinner V821B + AIC8800D80",
        crypto_flag="-k4",
        testcp_flag="-c=1",
        led_cfg="7-5",
        patched_appver="26122219.6071.2.LL",
        stock_relpath="stock/update_26101215.6071.2.img",
        out_relpath="build/update_aa_fixed.img",
    ),
    "5140": ModelProfile(
        model_id="5140",
        ly_project="ly5140",
        radio_desc="Allwinner V821B + Realtek RTL8733BS",
        crypto_flag="-k55",
        testcp_flag="-c=4",
        led_cfg="107-5",
        patched_appver="26122219.5140.2.LL",
        stock_relpath="stock/update_26101218.5140.2.img",
        out_relpath="build/update_5140_aa_fixed.img",
    ),
}


DEBUG_SHELL_BLOCK = """
# --- DEBUG BUILD ONLY: shell over HTTP (POST body = command) on :8080, telnetd on :2323 ---
mkdir -p /tmp/dbg/cgi-bin
cat > /tmp/dbg/cgi-bin/sh.cgi <<'DBGEOF'
#!/bin/sh
echo "Content-Type: text/plain"
echo ""
CMD=$(dd bs=1 count=${CONTENT_LENGTH:-0} 2>/dev/null)
sh -c "$CMD" 2>&1
DBGEOF
chmod 755 /tmp/dbg/cgi-bin/sh.cgi
(sleep 8; httpd -p 8080 -h /tmp/dbg; telnetd -l /bin/sh -p 2323) >/dev/null 2>&1 &
# --- END DEBUG ---
"""


def render_ly_link_sh(profile: ModelProfile, debug: bool = False) -> bytes:
    dbg = DEBUG_SHELL_BLOCK if debug else ""
    script = f"""#!/bin/sh
#LY_BOOT_MODE=$1
#LY_DEBUG_MODE=$2

echo "WORKDIR=$WORKDIR"
{dbg}
# LeanLink name for Wi-Fi and Bluetooth: CAR2-xxxx -> LeanLink-xxxx (mixed case fits the car's pairing banner). /etc/profile builds the names as
# $CUSTOM_NAME-<product_number>; product_number is a per-unit ID from the ly_misc_dev driver (derived from the chip),
# so the suffix keeps two boxes apart. Inherited by hostapd (lyhostapd), btapp, raaservice, CarPlay and the web UI.
for v in WIFI_NAME BT_NAME PRODUCT_NAME; do
\teval "n=\\$$v"
\tcase "$n" in *-*) export $v="LeanLink-${{n##*-}}" ;; esac
done

mkdir -p /tmp/app
ln -sf $WORKDIR/btapp.gatt /tmp/btapp.gatt
touch /tmp/ly_btkeep

if [ "$LY_BOOT_MODE" = "update" ]; then
\t# The vendor removed /mnt/UDISK/ly_linktype_aa here, so every update ended in CarPlay mode and Android
\t# phones lost Android Auto. LeanLink keeps the mode the box was in before the update.
\t$WORKDIR/lyUpdate.sh $WORKDIR &
\tcp $WORKDIR/lyLoadModule.sh /tmp/
\t/tmp/lyLoadModule.sh $LY_BOOT_MODE &
\techo 3 > /proc/sys/vm/drop_caches
\texit 0
fi

# Restart by itself once an uploaded update has been written. The vendor updater only reports state 3
# (white LED) and waits for a manual restart; when the phone loses the box Wi-Fi during the update nobody can
# send it, so the box would stay in that state until it is unplugged. Only a change to 3 seen during this boot
# (after 1 or 2) counts: a 3 that is already there at boot must never trigger a restart, or the box would loop.
# The attribute reads "3" or "ly_update_status=3" depending on the kernel build. The 8 s pause leaves time for
# a follow-up setting such as the Wi-Fi channel.
(
\tbusy=0
\twhile sleep 3; do
\t\tst=$(cat /sys/class/misc/ly_misc_dev/ly/update 2>/dev/null)
\t\tst=${{st##*=}}
\t\tcase "$st" in
\t\t1|2) busy=1 ;;
\t\t3)
\t\t\tif [ "$busy" = 1 ]; then
\t\t\t\tsleep 8
\t\t\t\tsync
\t\t\t\treboot
\t\t\t\tbreak
\t\t\tfi ;;
\t\tesac
\tdone
) &


# On first boot after flash or factory reset (rst=1), default to Android Auto so AA-only
# head units & PC DHU never deadlock in CarPlay mode. Subsequent iPhone <-> Android
# switches (where raaservice removes ly_linktype_aa or lylinkapp recreates it) work freely!
if [ ! -f /mnt/UDISK/ly_default_aa_done ]; then
\ttouch /mnt/UDISK/ly_linktype_aa
\ttouch /mnt/UDISK/ly_default_aa_done
fi
# The vendor setting id=set&aa=2 (cloud certificate + "force Android Auto") drops /mnt/UDISK/force_raa, which stock
# reads in AA mode only; honour it here so it also works from CarPlay mode (the LeanLink page offers only 0 and 1). Removing it keeps raaservice in pure HostAP mode.
if [ -f /mnt/UDISK/force_raa ]; then
\ttouch /mnt/UDISK/ly_linktype_aa
\trm -f /mnt/UDISK/force_raa
fi

if [ -f /mnt/UDISK/ly_linktype_aa ]; then
\tdate -s "2024-11-28 10:00:00"
\t# Unpack libssl.so.1.1 & libcrypto.so.1.1 from lylink, then immediately purge CarPlay binaries from RAMFS
\tlypack d $WORKDIR/lylink /tmp/app
\trm -f /tmp/app/libr*.so /tmp/app/rc*
\tcp -H $WORKDIR/raaservice \\
\t\t$WORKDIR/mtpservice \\
\t\t$WORKDIR/liblylinkmw.so.1 \\
\t\t$WORKDIR/libprotobuf-c.so.1 \\
\t\t$WORKDIR/my.ttf /tmp/app/

\tln -sf $WORKDIR/logo /tmp/raaui
\tln -sf $WORKDIR/raa.crt /tmp/app/raa.crt
\t$WORKDIR/lyUpdate.sh $WORKDIR &
\tcp $WORKDIR/lyLoadModule.sh /tmp/
\t/tmp/lyLoadModule.sh $LY_BOOT_MODE &

\t# USB UDC watchdog: recover automatically if SIGSYS leaves gadget unbound >=9s
\t(
\t\tdead=0
\t\twhile sleep 3; do
\t\t\tif [ -f /sys/kernel/config/usb_gadget/g1/UDC ]; then
\t\t\t\tudc=$(cat /sys/kernel/config/usb_gadget/g1/UDC 2>/dev/null)
\t\t\t\tif [ -z "$udc" ] || [ "$udc" = "none" ]; then
\t\t\t\t\tdead=$((dead + 1))
\t\t\t\t\tif [ "$dead" -ge 3 ]; then
\t\t\t\t\t\techo "44100000.udc-controller" > /sys/kernel/config/usb_gadget/g1/UDC 2>/dev/null
\t\t\t\t\t\tdead=0
\t\t\t\t\tfi
\t\t\t\telse
\t\t\t\t\tdead=0
\t\t\t\tfi
\t\t\tfi
\t\tdone
\t) &

\traaservice -B -w -d {profile.crypto_flag}
else
\techo "run carplay mode"
\tlypack d $WORKDIR/lylink /tmp/app
\tchmod 755 /tmp/app/rcpservice
\ttouch /tmp/ly_logo_cp
\ttouch /tmp/ly_tiph264_direct
\tlogwrapper mdnsd &
\tcp -Hr $WORKDIR/libdns_sd.so \\
\t\t$WORKDIR/my.ttf \\
\t\t$WORKDIR/logo /tmp/app/
\tlogwrapper $WORKDIR/ly_testcp {profile.testcp_flag} &
\tif [ -f /tmp/app/rcpservice ]; then
\t\tnice -n -9 /tmp/app/rcpservice {profile.crypto_flag} -ble > /dev/null 2>&1 &
\telse
\t\tnice -n -9 $WORKDIR/rcpservice {profile.crypto_flag} -ble > /dev/null 2>&1 &
\tfi
\t$WORKDIR/lyUpdate.sh $WORKDIR &
\tcp $WORKDIR/lyLoadModule.sh /tmp/
\t/tmp/lyLoadModule.sh $LY_BOOT_MODE &
\ttrial=0
\twhile [ ! -f "/tmp/lyrcpok" ] && [ $trial -le 50 ]; do
\t\tsleep 0.1
\t\ttrial=$((trial + 1))
\tdone
\tnice -n -15 $WORKDIR/lylinkapp -w &

\t# CarPlay -> Android Auto switch. In CarPlay mode btapp reports an Android phone opening the AA RFCOMM
\t# channel as "AA" on /dev/rf_serial, but no stock process reads it, so Android phones were locked out until
\t# a manual switch. Switch only when no CarPlay session is running (no established TCP connection besides
\t# loopback and the web UI ports 80/8080; a phone that merely joined the Wi-Fi does not count) and after a
\t# 25 s grace period, so an Android phone of a passenger cannot kick out a reconnecting iPhone.
\tcp_session() {{
\t\tcat /proc/net/tcp /proc/net/tcp6 2>/dev/null | awk '$4 == "01" {{ split($2, a, ":");
\t\t\tif (a[1] != "0100007F" && a[1] != "00000000000000000000000001000000" && a[2] != "0050" && a[2] != "1F90") n++ }}
\t\t\tEND {{ exit (n > 0) ? 0 : 1 }}'
\t}}
\t(
\t\twhile [ ! -e /dev/rf_serial ]; do sleep 1; done
\t\twhile read -r line; do
\t\t\tcase "$line" in
\t\t\tAA*)
\t\t\t\tup=$(cut -d. -f1 /proc/uptime)
\t\t\t\tif [ "$up" -ge 25 ] && ! cp_session; then
\t\t\t\t\techo "lyLink: Android phone requested AA in CarPlay mode, switching"
\t\t\t\t\ttouch /mnt/UDISK/ly_linktype_aa
\t\t\t\t\tsync
\t\t\t\t\treboot
\t\t\t\tfi
\t\t\t\t;;
\t\t\tesac
\t\tdone < /dev/rf_serial
\t) &
fi

echo 3 > /proc/sys/vm/drop_caches
"""
    return script.encode("ascii")


PATCHED_BLINK_SH = b"""#!/bin/sh

BTAPP="$WORKDIR/btapp"

echo 0 > /sys/devices/virtual/misc/ly_misc_dev/ly/bt_rst

if echo "$BT_NAME" | grep -q ' '; then
    BT_ARG="-N$BT_NAME"
else
    BT_ARG=-N$BT_NAME
fi

# Start Classic BR/EDR stack only (debloated: no AT#LR fake BLE MAC, no otto_goc scan spam)
nice -n -16 "$BTAPP" "$BT_ARG" -T/dev/ttyS1 -B -M
"""


PATCHED_LY_LOAD_MODULE_SH = b"""#!/bin/sh

#LY_BOOT_MODE=$1
WIFIPATH=/etc/wifi

if [ -f /tmp/ap_p2p_mixed ]; then
\tkillall hostapd 2>/dev/null
\tkillall udhcpd 2>/dev/null
\tkillall wpa_supplicant 2>/dev/null
\tkillall p2p_wps_pbc.sh 2>/dev/null
\tsleep 1
\tkillall -9 udhcpd 2>/dev/null
\tkillall -9 wpa_supplicant 2>/dev/null
\tkillall -9 hostapd 2>/dev/null
fi

if [ -f /sys/ly_private/wifi_ch ]; then
\twifi_ch=$(cat /sys/ly_private/wifi_ch)
\techo "wifi_ch=$wifi_ch"
\tif [ "$wifi_ch" != "0" ] && [ -n "$wifi_ch" ]; then
\t\texport WIFI_AP_CH=$wifi_ch
\tfi
fi

if [ -z "$WIFI_AP_CH" ] || [ "$WIFI_AP_CH" = "0" ]; then
\texport WIFI_AP_CH=36
fi

if [ -z "$IPADDR" ]; then
\texport IPADDR=192.168.1.101
fi
if [ -z "$SUBNETMASK" ]; then
\texport SUBNETMASK=255.255.255.0
fi

if [ -f "$WORKDIR/udhcpd-cp.conf" ]; then
\tcp -rf "$WORKDIR/udhcpd-cp.conf" /tmp/udhcpd_ap.conf
else
\tcp -rf "$WIFIPATH/udhcpd-cp.conf" /tmp/udhcpd_ap.conf
fi
# Fix Bug B: raaservice (src/wpa.c) reads & rewrites /tmp/udhcpd.conf directly
cp -rf /tmp/udhcpd_ap.conf /tmp/udhcpd.conf

if [ ! -f /tmp/blink ]; then
\tblink.sh ${LY_BOOT_MODE} ${LY_DEBUG_MODE} &
\ttouch /tmp/blink
fi

wlan0=$(ifconfig -a | grep wlan0)
trial=0
while [ -z "$wlan0" ] && [ $trial -le 40 ]; do
\tsleep 0.2
\ttrial=$((trial + 1))
\twlan0=$(ifconfig -a | grep wlan0)
done

if [ $trial -gt 40 ]; then
\techo "wlan0 not found"
\texit 1
fi

mkdir -p /var/wifi/misc
mkdir -p /var/run/hostapd/
mkdir -p /var/run/wpa_supplicant
rm -f /dev/random
ln -s /dev/urandom /dev/random
echo 1 > /proc/sys/net/ipv6/conf/wlan0/disable_ipv6
ifconfig wlan0 up
ifconfig wlan0 $IPADDR netmask $SUBNETMASK
sleep 1

# Pure 5 GHz HostAP mode (Huawei HiCar P2P / wpa_supplicant / WPS PBC bloat removed)
rm -fr /tmp/ap_p2p_mixed
lyhostapd
touch /tmp/ap_p2p_mixed

logwrapper udhcpd /tmp/udhcpd.conf &

echo 3 > /proc/sys/vm/drop_caches
"""


PATCHED_OTTO_STUB = b"#!/bin/sh\nexit 0\n"


def render_system_json(profile: ModelProfile, debug: bool = False) -> bytes:
    payload = {
        "align": "right|bottom",
        "color": "#ffffff",
        # Debug images report e.g. 26122204.5140.2.LL-debug (project ID stays field 2 of the dotted version)
        "appver": profile.patched_appver + ("-debug" if debug else ""),
        "led": profile.led_cfg,
    }
    return (json.dumps(payload) + "\n").encode("ascii")


WEBUI_DIR = Path(__file__).resolve().parent / "webui"


LL_CSS = """
		:root { --ll: #0b1220; --ll2: #a3e635; --ll-ink: #4d7c0f; --ll-soft: #f3f8e8; --ll-bg: #f3f4f6; --ll-text: #111827; --ll-muted: #64748b; --ll-line: #e5e7eb; }
		body { background: var(--ll-bg); color: var(--ll-text); font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
		.page { background: var(--ll-bg); padding-bottom: 8px; }
		.ll-hero { display: flex; align-items: center; gap: 14px; padding: 22px 18px 20px; color: #fff;
			background: linear-gradient(135deg, #0b1220 0%, #111a2e 55%, #1e293b 100%); border-radius: 0 0 22px 22px;
			box-shadow: 0 6px 18px rgba(11, 18, 32, .35); border-bottom: 2px solid #a3e635; margin-bottom: 6px; }
		.ll-hero svg { flex: none; width: 56px; height: 56px; filter: drop-shadow(0 3px 6px rgba(0,0,0,.18)); border-radius: 16px; }
		.ll-name { font-size: 1.55rem; font-weight: 700; letter-spacing: .01em; line-height: 1.1; }
		.ll-sub { font-size: .8rem; color: #cbd5e1; line-height: 1.4; margin-top: 3px; }
		.ll-chip { display: inline-block; margin-top: 6px; padding: 2px 9px; border-radius: 999px; background: rgba(163,230,53,.16);
			font-size: .75rem; color: #d9f99d; }
		.cells { width: auto !important; box-sizing: border-box; background: #fff; margin: 12px 12px 0; border-radius: 14px; overflow: hidden; box-shadow: 0 1px 3px rgba(16, 42, 40, .08); }
		.title { margin: 0; padding: 14px 16px 6px; background: transparent; color: var(--ll-ink); font-size: .78rem; font-weight: 650;
			text-transform: uppercase; letter-spacing: .07em; }
		.weui-cell { color: var(--ll-text); font-size: .95rem; }
		.weui-cell:before { border-top-color: var(--ll-line); left: 16px; }
		.weui-cell__ft { color: var(--ll-muted); }
		.weui-cells__title { color: var(--ll-muted) !important; font-size: .85rem; }
		.weui-cells { margin-top: 4px; }
		.weui-input::placeholder, .weui-textarea::placeholder { color: #a9b6b4; }
		.weui-btn { border-radius: 10px; font-size: 1rem; font-weight: 600; }
		.weui-btn_primary, .weui-btn_primary:not(.weui-btn_disabled):active { background-color: var(--ll); }
		.weui-btn_primary.weui-btn_disabled { background-color: #cbd5e1; color: #fff; }
		.cells > .weui-btn { width: auto; margin: 12px 16px 16px; }
		.weui-footer { padding: 18px 0 10px; }
		.weui-footer__text { color: var(--ll-muted); font-size: .75rem; }
		.weui-picker__action, .weui-dialog__btn_primary { color: var(--ll-ink) !important; }
		.ll-card { padding: 4px 16px 16px; }
		.ll-note { font-size: .875rem; color: var(--ll-muted); line-height: 1.5; margin-bottom: 10px; }
		.ll-card input[type=file] { display: block; width: 100%; margin: 8px 0 10px; font-size: .9rem; padding: 10px;
			border: 1.5px dashed #bef264; border-radius: 10px; background: var(--ll-soft); box-sizing: border-box; }
		.ll-info, .ll-sta { font-size: .875rem; margin: 8px 0; min-height: 1.2em; line-height: 1.45; }
		.ll-help { font-size: .78rem; color: var(--ll-muted); line-height: 1.4; margin-top: 2px; padding-right: 8px; }
		.ll-ok { color: var(--ll-ink); } .ll-bad { color: #b42318; }
		.ll-link { display: inline-block; margin: 6px 12px 0 0; color: var(--ll-ink); font-size: .875rem; font-weight: 600; }
		.ll-card .weui-progress { margin: 10px 0 4px; }
		.ll-card .weui-progress__bar { background-color: var(--ll-line); border-radius: 4px; overflow: hidden; height: 4px; }
		.ll-card .weui-progress__inner-bar { background-color: var(--ll2); }
"""


LL_HERO = """
	<div class="ll-hero">
		@@LOGO@@
		<div><div class="ll-name">LeanLink</div>
		<div class="ll-sub" id="ll_sub">Wireless Android Auto &amp; CarPlay &middot; debloated</div>
		<span class="ll-chip" id="ll_ver"></span></div>
	</div>"""


LL_FW_CARD = """	<div class="cells">
		<div class="title" id="ll_fwtitle">Firmware update</div>
		<div class="ll-card">
			<p class="ll-note" id="ll_note">Online updates from the vendor are disabled: they would replace LeanLink with the stock
			firmware. Upload a firmware file instead (LeanLink or stock); it is checked in the browser before it is
			sent. This box: <b id="ll_dev"></b>.</p>
			<div id="ll_online" class="ll-info"></div>
			<input type="file" id="ll_file" accept=".img,application/octet-stream" onchange="llCheck(this.files[0])">
			<div id="ll_info" class="ll-info"></div>
			<a href="javascript:llFlash();" class="weui-btn weui-btn_primary weui-btn_disabled" id="ll_go">Upload and install</a>
			<div class="weui-progress"><div class="weui-progress__bar"><div class="weui-progress__inner-bar" id="ll_prog" style="width: 0%;"></div></div></div>
			<p id="ll_sta" class="ll-sta"></p>
		</div>
	</div>
"""


DEFAULT_REPO = "lachyn/leanlink"  # GitHub owner/repo: release page and issue tracker of LeanLink


VENDOR_CLOUD_FUNCS = ("download_fw", "ontfw", "update_fw", "upload_fw", "update_log", "update_sts", "getOSSCli",
                      "cpbox_geturl", "aa_update")


UNUSED_VENDOR_ROWS = ("div_mod", "ly1301", "div_mic", "div_mouse", "div_icon", "div_conn", "div_hi", "div_led2", "div_dis")


def _drop_js_function(js: str, name: str) -> str:
    """Remove `function name(...) {...}` (or async) from vendor JS by brace matching."""
    for head in (f"async function {name}(", f"function {name}("):
        i = js.find(head)
        if i < 0:
            continue
        j = js.index("{", i)
        depth = 0
        for k in range(j, len(js)):
            if js[k] == "{":
                depth += 1
            elif js[k] == "}":
                depth -= 1
                if depth == 0:
                    return js[:i] + f"/* LeanLink: vendor cloud function {name}() removed */" + js[k + 1:]
    raise AssertionError(f"vendor function {name} not found")


def strip_vendor_cloud(cpbox_js: str) -> str:
    """No request to the vendor cloud: drop OTA download, cloud log upload, STS credentials, cloud certificate."""
    js = cpbox_js.replace("\r\n", "\n")
    for name in VENDOR_CLOUD_FUNCS:
        js = _drop_js_function(js, name)
    js = _drop_js_function(js, "cpbox_init")
    js += "\nfunction cpbox_init(j) { txt = j.res.val; }\n"
    js = js.replace("var timer_8min = function", "var timer_8min_unused = function")
    for bad in ("aliyuncs", "cpbox-abroad", "oss-us-west", "oss-cn-shenzhen", "OSS("):
        assert bad not in js, f"vendor cloud reference left in cpbox.js: {bad}"
    return js


def patch_webui(index_html: bytes, cpbox_js: bytes, repo: str = DEFAULT_REPO) -> tuple[bytes, bytes]:
    """Brand the vendor web UI as LeanLink, disable vendor online updates, add verified local upload."""
    html = index_html.decode("utf-8").replace("\r\n", "\n")
    logo = (WEBUI_DIR / "logo.svg").read_text().strip()
    logo = logo.replace(' width="64" height="64"', "", 1)  # only on <svg>, keep the <rect> size

    def sub(old: str, new: str) -> None:
        nonlocal html
        assert html.count(old) == 1, f"web UI anchor not found exactly once: {old[:60]!r}"
        html = html.replace(old, new)

    import urllib.parse
    fav = "data:image/svg+xml," + urllib.parse.quote(logo, safe=" =:/\"")
    sub('\t<script src="/js/aliyun-oss-sdk.min.js"></script>\n', "")
    sub("                aa_update();\n", "                /* LeanLink: vendor cloud certificate refresh disabled */\n")
    # Lean: drop every vendor row this firmware does not use or that has no known effect (other products'
    # features, hidden form fields), so the page shows only settings LeanLink can explain.
    import re as _re
    for row in UNUSED_VENDOR_ROWS:
        html, n = _re.subn(r'\t\t<a class="weui-cell weui-cell_access" id="' + row + r'"[^>]*>\n(?:\t\t\t.*\n)*?\t\t</a>\n', "", html)
        assert n == 1, f"vendor row {row} not found"
    html, n = _re.subn(r'\t\t<div class="weui-cell log7">\n(?:\t\t\t.*\n){2}\t\t</div>\n', "", html)
    assert n == 3, f"expected 3 hidden head-unit fields, found {n}"
    # The vendor's generic option labels would flash before leanlink.js fills in real ones.
    for old_arr, new_arr in (("var ledlb = ['开启', '关闭'];", "var ledlb = ['', ''];"),
                             ("var lb2 = ['Default', 'Mode 1'];", "var lb2 = ['', ''];"),
                             ("var lb3 = ['Default', 'Mode 1', 'Mode 2'];", "var lb3 = ['', '', ''];"),
                             ("var lb4 = ['Default', 'Mode 1', 'Mode 2', 'Mode 3'];", "var lb4 = ['', '', '', ''];")):
        sub(old_arr, new_arr)
    # vendor code that touches removed rows without a null check
    sub("\t\t\tdocument.getElementById('div_mod').style.display = \"none\";\n", "")
    sub("\t\t\t\tdocument.getElementById('div_icon').style.display = \"none\";\n", "")
    sub('{label: "默认", value: "aoa"}', '{label: "Android Auto", value: "aoa"}')  # unused vendor picker
    leftover = _re.findall(r"[\u4e00-\u9fff]+", html)
    assert not leftover, f"Chinese text left: {leftover}"
    assert not _re.search(r"Mode [0-9]", html), "generic 'Mode N' label left in index.html"
    sub("<title> </title>", f'<title>LeanLink</title>\n\t<link rel="icon" href="{fav}">\n\t<meta name="theme-color" content="#0b1220">')
    sub("\t\t.hide {display: none;}\n", "\t\t.hide {display: none;}\n" + LL_CSS)
    sub('<script type="text/html" id="tpl_home">\n<div class="page">',
        '<script type="text/html" id="tpl_home">\n<div class="page">' + LL_HERO.replace("@@LOGO@@", logo))
    start = html.index('\t<div class="cells">\n\t\t<div class="title" id="txt10"></div>')
    end = html.index('\t<div class="weui-footer">', start)
    html = html[:start] + LL_FW_CARD + html[end:]
    sub("\t\t\tqueryNewVer();\n", "\t\t\tllInit(j);\n")
    # LeanLink versions end with ".LL"; read the project ID by field instead of fixed character positions.
    sub("appver = j.sys.appver.slice(-6, -2);", "appver = (j.sys.appver.split('.')[1] || '');")
    # Problem report goes to the LeanLink issue tracker (saved locally, redacted), not to the vendor cloud.
    sub('<a href="javascript:onCommit();" class="weui-btn weui-btn_primary" id="txt9"></a>',
        '<a href="javascript:llReport();" class="weui-btn weui-btn_primary" id="ll_report"><span id="txt9_ll">Save problem report</span></a><p id="ll_rep_sta" class="ll-sta" style="padding: 0 15px;"></p>')
    sub("Copyright©2020 - 2028",
        f'LeanLink &middot; <a href="https://github.com/{repo}" target="_blank" style="color: inherit;">github.com/{repo}</a>'
        ' &middot; <span id="ll_foot">not affiliated with the vendor</span>')
    # The vendor page had hidden Chinese labels and no language, so Chrome offered "translate from Chinese"; with
    # those gone and lang=en it offers a proper translation into the phone's language.
    sub("<html>", '<html lang="en">')  # browsers offer an English -> user language translation

    key_hex = lo.V821_KEY.hex()
    js = (WEBUI_DIR / "leanlink.js").read_text().replace("@@KEY@@", key_hex)
    js = js.replace("@@LATEST@@", f"https://github.com/{repo}/releases/latest")
    js = js.replace("@@ISSUES@@", f"https://github.com/{repo}/issues/new")
    import json as _json
    tr = {f.stem: _json.loads(f.read_text(encoding="utf-8")) for f in sorted((WEBUI_DIR / "i18n").glob("*.json"))}
    assert "en" in tr and all(set(d) == set(tr["en"]) for d in tr.values()), "i18n dictionaries must share the keys of en.json"
    js = js.replace("@@I18N@@", _json.dumps(tr, ensure_ascii=False, separators=(",", ":")))
    assert "@@" not in js
    vendor_js = strip_vendor_cloud(cpbox_js.decode("utf-8"))
    import re as _re
    assert not _re.search(r"[\u4e00-\u9fff]", html), "Chinese text left in index.html"
    return html.encode("utf-8"), vendor_js.rstrip("\n").encode("utf-8") + b"\n\n" + js.encode("utf-8")


def check_requirements() -> None:
    missing = [tool for tool in ("unsquashfs", "mksquashfs") if shutil.which(tool) is None]
    if missing:
        raise SystemExit("Missing requirements: " + ", ".join(missing) + " (see docs/BUILDING.md)")


def build_for_profile(profile: ModelProfile, stock_img: Path, out_img: Path, repo: str = DEFAULT_REPO,
                      debug: bool = False) -> None:
    out_img.parent.mkdir(parents=True, exist_ok=True)
    print(f"=== Building {profile.ly_project} ({profile.radio_desc}) from {stock_img}{' [DEBUG]' if debug else ''} ===")

    swu = lo.unwrap_envelope(lo.decrypt(stock_img.read_bytes()))
    archive = lo.CpioArchive.parse(swu)  # also proves a byte-identical re-pack of the stock archive
    lo.validate_sw_description(archive.member("sw-description"), profile.ly_project)

    orig_customer = archive.member("customer")
    orig_info = lo.squashfs_info(orig_customer)

    with tempfile.TemporaryDirectory(prefix=f"leanlink-{profile.model_id}-") as tmp:
        ws = Path(tmp)
        orig_sqfs = ws / "orig.sqfs"
        new_sqfs = ws / "new.sqfs"
        root = ws / "root"
        orig_sqfs.write_bytes(orig_customer)

        subprocess.run(
            ["unsquashfs", "-no-xattrs", "-ignore-errors", "-no-exit-code", "-d", str(root), str(orig_sqfs)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        replacements = {
            root / "app" / "lyLink.sh": (render_ly_link_sh(profile, debug), 0o755),
            root / "app" / "blink.sh": (PATCHED_BLINK_SH, 0o755),
            root / "app" / "lyLoadModule.sh": (PATCHED_LY_LOAD_MODULE_SH, 0o755),
            root / "app" / "otto_goc": (PATCHED_OTTO_STUB, 0o755),
            root / "app" / "system.json": (render_system_json(profile, debug), 0o755),
        }
        web = root / "ota" / "www"
        new_html, new_js = patch_webui((web / "index.html").read_bytes(), (web / "js" / "cpbox.js").read_bytes(), repo)
        replacements[web / "index.html"] = (new_html, (web / "index.html").stat().st_mode & 0o777)
        replacements[web / "js" / "cpbox.js"] = (new_js, (web / "js" / "cpbox.js").stat().st_mode & 0o777)
        # The vendor translation files stay as they are, except Russian, Chinese and Arabic, which get the English texts
        # (owner's decision; the files must stay because the SquashFS inode count is fixed). LeanLink's own texts come in
        # several languages from leanlink.js. The unused date-picker suffixes go from the WeUI library.
        for gone in ("ru-RU.json", "zh-CN.json", "zh-TW.json", "ar-SA.json"):  # no Russian, Chinese, Arabic (owner)
            lan = web / "lan" / gone
            replacements[lan] = ((web / "lan" / "en-US.json").read_bytes(), lan.stat().st_mode & 0o777)
        weui = (web / "js" / "weui.min.js").read_text(encoding="utf-8")
        for cjk in ("年", "月", "日"):
            weui = weui.replace(cjk, "")
        replacements[web / "js" / "weui.min.js"] = (weui.encode("utf-8"), (web / "js" / "weui.min.js").stat().st_mode & 0o777)
        import re as _re
        for path, (data, _mode) in replacements.items():
            if web in path.parents and path.suffix in (".html", ".css", ".json") or path.name == "weui.min.js":
                left = _re.findall(r"[\u4e00-\u9fff]", data.decode("utf-8", "ignore"))
                assert not left, f"Chinese text left in {path.name}: {left[:5]}"
        for png in sorted(SPLASH_DIR.glob("*.png")):
            target = root / "app" / "logo" / png.name
            if target.is_file():
                replacements[target] = (png.read_bytes(), target.stat().st_mode & 0o777)

        for target, (data, mode) in replacements.items():
            assert target.is_file() and not target.is_symlink(), f"Missing target {target}"
            st = target.stat()
            target.write_bytes(data)
            os.chmod(target, mode)
            os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))

        console_time = int((root / "dev").stat().st_mtime)
        subprocess.run(
            [
                "mksquashfs",
                str(root),
                str(new_sqfs),
                "-noappend",
                "-comp",
                "xz",
                "-b",
                str(orig_info.block_size),
                "-all-root",
                "-no-tailends",
                "-exports",
                "-no-xattrs",
                "-mkfs-time",
                str(orig_info.mkfs_time),
                "-processors",
                "1",
                "-no-progress",
                "-p",
                f"dev/console C {console_time} 600 0 0 5 1",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        new_customer = new_sqfs.read_bytes()
        new_info = lo.squashfs_info(new_customer)
        assert new_info.inodes == orig_info.inodes, f"Inode count changed: {new_info.inodes} != {orig_info.inodes}"
        assert len(new_customer) <= CUSTOMER_SIZE_LIMIT, f"Customer too big: {len(new_customer)} > {CUSTOMER_SIZE_LIMIT}"

        print(f"Original customer SquashFS: {len(orig_customer):,} bytes (inodes={orig_info.inodes})")
        print(f"Patched  customer SquashFS: {len(new_customer):,} bytes (inodes={new_info.inodes})")

    archive.replace("customer", new_customer)
    new_swu = archive.pack()
    reparsed = lo.CpioArchive.parse(new_swu)
    lo.validate_sw_description(reparsed.member("sw-description"), profile.ly_project)

    out_img.write_bytes(lo.encrypt(lo.wrap_envelope(new_swu)))

    # Full round trip of the written file
    verify = lo.CpioArchive.parse(lo.unwrap_envelope(lo.decrypt(out_img.read_bytes())))
    assert verify.member("customer") == new_customer
    assert verify.member("kernel") == archive.member("kernel")
    print(f"SUCCESS: wrote and verified {out_img} ({out_img.stat().st_size:,} bytes, appver={profile.patched_appver}{'-debug' if debug else ''})")
    if debug:
        print("WARNING: debug image. Anyone on the box Wi-Fi (public password) gets a root shell on port 8080.\n"
              "         Use it only on your own box and flash the normal image afterwards (docs/BUILDING.md).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the LeanLink firmware from a stock vendor OTA.")
    parser.add_argument("--model", choices=["6071", "5140", "all"], default="all",
                        help="project ID of the adapter: 6071, 5140 or all (default: all)")
    parser.add_argument("--stock", type=Path,
                        help="stock OTA to patch (only with a single --model; default: stock/<vendor file name>)")
    parser.add_argument("--out", type=Path,
                        help="output image (only with a single --model; default: build/<image name>)")
    parser.add_argument("--debug", action="store_true",
                        help="research only: add a root shell over HTTP on port 8080 (no password) and telnetd on "
                             "2323 if available; appver ends with .LL-debug, output *_debug.img (docs/BUILDING.md)")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"GitHub owner/repo for the release link and problem reports (default {DEFAULT_REPO})")
    args = parser.parse_args()

    targets = ["6071", "5140"] if args.model == "all" else [args.model]
    if len(targets) > 1 and (args.stock or args.out):
        parser.error("--stock and --out need a single --model")
    check_requirements()

    built = 0
    for model_id in targets:
        profile = PROFILES[model_id]
        stock = args.stock or BASE / profile.stock_relpath
        out = args.out or BASE / profile.out_relpath
        if args.debug and not args.out:
            out = out.with_name(out.stem + "_debug.img")
        if not stock.is_file():
            if args.model != "all":
                raise SystemExit(f"Missing stock OTA image: {stock} (see docs/BUILDING.md)")
            print(f"SKIP {profile.ly_project}: {stock} not present")
            continue
        build_for_profile(profile, stock, out, args.repo, args.debug)
        built += 1
    if not built:
        raise SystemExit("Nothing built: put the stock OTA images into stock/ (see docs/BUILDING.md)")


if __name__ == "__main__":
    main()
