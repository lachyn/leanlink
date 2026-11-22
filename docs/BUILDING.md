# Building LeanLink yourself

The builder turns the vendor's stock update image into the LeanLink image. Vendor firmware is not stored in
this repository, so you download the stock image from the vendor first. With the same stock image and the same
tool versions the result is byte-identical to the published release.

## Contents

- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [1. Get the stock firmware](#1-get-the-stock-firmware)
- [2. Build](#2-build)
- [3. What the builder checks](#3-what-the-builder-checks)
- [4. Verify a release](#4-verify-a-release)
- [5. Changing LeanLink](#5-changing-leanlink)
- [Research and debugging](#research-and-debugging)
  - [Running commands](#running-commands)
  - [Useful places on the adapter](#useful-places-on-the-adapter)
  - [Pitfalls](#pitfalls)
  - [Going back](#going-back)
- [Maintainers: publishing a release](#maintainers-publishing-a-release)

## Repository layout

```text
tools/build_patched_ota.py    builder: all firmware changes (scripts inline), web UI patch, packing
tools/leanlink_ota.py         OTA container: V821 encryption, MD5 envelope, CPIO, SquashFS and sw-description checks
tools/webui/                  web UI additions (leanlink.js) and logo
tools/branding/png/           LeanLink splash screens (ready-made PNGs, copied into the image)
tools/decode_logcat.py        decoder for the adapter's system log download
tools/box_shell.sh            runs commands on an adapter with a debug image (research only)
flash.sh, flash_windows.bat   command-line flashers (Linux / macOS / Android, Windows)
flasher.html                  upload form for any browser
tools/release.sh              maintainer script: build and create the GitHub release
stock/                        put the vendor's stock images here to build (git-ignored)
docs/                         flashing guide, settings, building, how it works
```

## Requirements

- Linux (tested on Ubuntu 24.04 / Linux Mint) or macOS
- Python 3.10 or newer
- `squashfs-tools` 4.5+ (`unsquashfs`, `mksquashfs`, with xz support)

```bash
# Debian / Ubuntu / Mint
sudo apt install python3 squashfs-tools

# macOS (Homebrew)
brew install python squashfs
```

## 1. Get the stock firmware

The vendor publishes its updates in a public bucket, one folder per project. The `version.json` next to each
image names the version currently offered:

| Project | Version manifest | Stock image | Save as |
|---|---|---|---|
| `ly6071` | <https://cpbox-abroad.oss-us-west-1.aliyuncs.com/6071/version.json> | <https://cpbox-abroad.oss-us-west-1.aliyuncs.com/6071/update.img> | `stock/update_26101215.6071.2.img` |
| `ly5140` | <https://cpbox-abroad.oss-us-west-1.aliyuncs.com/5140/version.json> | <https://cpbox-abroad.oss-us-west-1.aliyuncs.com/5140/update.img> | `stock/update_26101218.5140.2.img` |

```bash
curl -s https://cpbox-abroad.oss-us-west-1.aliyuncs.com/5140/version.json     # "appver": "26101218.5140.2"
curl -o stock/update_26101218.5140.2.img https://cpbox-abroad.oss-us-west-1.aliyuncs.com/5140/update.img
curl -o stock/update_26101215.6071.2.img https://cpbox-abroad.oss-us-west-1.aliyuncs.com/6071/update.img
sha256sum stock/*.img
```

LeanLink is built and tested against exactly these stock versions:

| File | Size | SHA-256 |
|---|---|---|
| `update_26101215.6071.2.img` | 6,676,525 | `02d082a3463604af51f055049cb95a2f8baba13b105e80c758c6893d6c18c220` |
| `update_26101218.5140.2.img` | 6,948,909 | `ab6b4962f1e31d423c21f02bcb5e191377db1eb7ea47bc0c59fd442a65e01442` |

If `version.json` offers a newer version than the one above, the vendor has changed the firmware. The builder
still checks the image structure, but the replaced scripts were written for the versions listed here; test such
a build carefully (and please open an issue).

## 2. Build

```bash
python3 tools/build_patched_ota.py --model all     # or --model 6071 / --model 5140
```

Output: `build/update_aa_fixed.img` (ly6071) and `build/update_5140_aa_fixed.img` (ly5140).

Options:

| Option | Meaning |
|---|---|
| `--model 6071\|5140\|all` | Which project to build (default `all`; models without a stock image are skipped). |
| `--stock PATH` | Use this stock image instead of `stock/<name>` (single model only). |
| `--out PATH` | Write the result here instead of `build/<name>` (single model only). |
| `--debug` | Research only: adds a root shell over HTTP (no password). See [Research and debugging](#research-and-debugging). |
| `--repo OWNER/REPO` | GitHub repository the adapter's web UI links to (newest release, problem reports) (default `lachyn/leanlink`). Set it to your fork if you publish your own builds. |

## 3. What the builder checks

Every build stops with an error unless all of this holds:

1. the stock image decrypts to a valid archive (the last entry must be the CPIO trailer);
2. the MD5 in the `update.swu` header matches the archive;
3. every CPIO member checksum matches, and the stock archive re-packs byte-identically;
4. `sw-description` has the vendor magic `0xAA55A55A`, the expected project (`ly6071` / `ly5140`) and writes
   only `kernel` → `boot` and `customer` → `customer`;
5. the rebuilt `customer` SquashFS uses the original block size and timestamp, has the same number of inodes and
   fits the 3,801,088-byte partition;
6. the written image is decrypted and unpacked again, and its `customer` and `kernel` are compared with what was
   meant to be written.

## 4. Verify a release

To check that a published image was built from this source:

```bash
python3 tools/build_patched_ota.py --model 5140
sha256sum build/update_5140_aa_fixed.img leanlink-5140-*-LL.img     # must be identical
```

The SHA-256 of each image is listed in its release notes. Reproducible results were verified with
squashfs-tools 4.6.1 on Ubuntu 24.04; another `mksquashfs` version (compression) can produce a working image
with a different checksum.

You can also look inside an image:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "tools")
import leanlink_ota as lo
arc = lo.CpioArchive.parse(lo.unwrap_envelope(lo.decrypt(open("build/update_5140_aa_fixed.img", "rb").read())))
open("customer.sqfs", "wb").write(arc.member("customer"))
print(arc.member("sw-description").decode())
EOF
unsquashfs -d customer customer.sqfs && cat customer/app/system.json
```

## 5. Changing LeanLink

- Start scripts, profiles per model and the web UI patch: `tools/build_patched_ota.py` (the scripts are inline,
  so a diff of the builder is a diff of the firmware).
- Web UI behaviour and texts: `tools/webui/leanlink.js`.
- Splash screens: replace the PNGs in `tools/branding/png/` (same file names and sizes; 256-colour PNGs keep the
  partition small enough).
- OTA container format: `tools/leanlink_ota.py`.

Bump `patched_appver` in `PROFILES` for every build you distribute; versions must end with `.LL` and compare
as strings (`YYMMDDHH.<project>.2.LL`).

## Research and debugging

For measuring and experimenting on **your own** adapter, the builder can produce a debug image:

```bash
python3 tools/build_patched_ota.py --model 5140 --debug     # → build/update_5140_aa_fixed_debug.img
```

It is the normal LeanLink image plus a root shell over HTTP: about 8 s after boot a busybox `httpd` listens on
port 8080, and `POST /cgi-bin/sh.cgi` runs the request body as a shell command as root and returns its output.
The builder also tries `telnetd` on port 2323, but the stock busybox has no telnetd, so in practice only the HTTP
shell exists. The version shown on the settings page ends with `.LL-debug` (for example
`26122213.5140.2.LL-debug`) so a debug box is easy to recognise.

> **Warning.** The debug shell has **no password**. Anyone who joins the adapter's Wi-Fi gets full root access,
> and the Wi-Fi password `88888888` is printed on every box and in this README. Use a debug image only on your own
> adapter, only while you need it, never give it to anyone else, and **flash the normal image afterwards**.
> `tools/release.sh` refuses to publish debug images.

Flash it like any other image (`sh flash.sh build/update_5140_aa_fixed_debug.img`, the settings page or
`flasher.html`).

### Running commands

[`tools/box_shell.sh`](../tools/box_shell.sh) sends a command and prints the output; every command and its
output is also appended to `./leanlink-shell.log` (follow it with `tail -f` in another terminal).

```bash
tools/box_shell.sh -d 'free'                       # -d: this computer is joined to the box Wi-Fi
tools/box_shell.sh -d 'ps w'
tools/box_shell.sh -d 'logcat -d | tail -50'
tools/box_shell.sh -d 'cat /proc/uptime'
curl --data-binary 'uname -a' http://192.168.1.101:8080/cgi-bin/sh.cgi   # the same without the script
```

**No 5 GHz Wi-Fi on the computer?** Without `-d` the script goes through an Android phone connected over USB
with USB debugging on: the phone joins the adapter's Wi-Fi and runs `curl --interface wlan0 …` via `adb shell`,
so mobile data on the phone does not get in the way.

```bash
adb devices                                        # phone listed
tools/box_shell.sh 'free; cat /tmp/hostapd.conf'
```

Environment variables: `LEANLINK_DIRECT=1` (same as `-d`), `LEANLINK_IP` (default `192.168.1.101`),
`LEANLINK_SHELL_LOG` (log file).

### Useful places on the adapter

| Path / command | What |
|---|---|
| `/mnt/customer/app` | the application: start scripts, vendor programs, `system.json`, `logo/` (read-only) |
| `/mnt/UDISK` | writable data: Bluetooth pairings, mode flags (`ly_linktype_aa`, `ly_default_aa_done`, `force_raa`) |
| `/tmp/hostapd.conf` | the Wi-Fi access point configuration generated at boot |
| `/tmp/udhcpd.conf` | DHCP configuration for the phone |
| `/tmp/app` | programs unpacked to RAM for the current mode |
| `logcat -d`, `dmesg` | system and kernel log |
| `free`, `top -b -n 1`, `cat /proc/loadavg` | memory and CPU load |

### Pitfalls

- **Never run `find /sys` or read arbitrary files under `/sys`.** Some of them hang the kernel; the watchdog
  then reboots the adapter.
- The adapter reboots whenever an Android Auto session drops (the vendor service restarts the box); the shell is
  back about 10 s after the Wi-Fi reappears.
- Everything outside `/mnt/UDISK` is read-only or in RAM and gone after a reboot.

### Going back

Flash the normal image (`build/update_5140_aa_fixed.img` or a release) the same way. The debug shell is gone
after that reboot; the version no longer ends with `-debug`.

## Maintainers: publishing a release

A release is a GitHub release with the tag `<YYMMDDHH>-LL` and these files attached:
`leanlink-<model>-<YYMMDDHH>-LL.img` for both models, `flasher.html`, `flash.sh` and `flash_windows.bat`.

```bash
sh tools/release.sh --notes "Fixes ..."              # dry run: build, prepare build/release/, print the command
sh tools/release.sh --notes "Fixes ..." --publish    # gh release create
```

Before publishing, a guard checks `build/release/`: only the files above are allowed, each image must differ
from every image in `stock/` and must contain a LeanLink release version (`appver` ending with `.LL`; debug
images are refused). **The vendor's stock images are never attached.** Requirements for publishing: push
access to the repository and `gh auth login`.
