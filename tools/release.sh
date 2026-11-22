#!/bin/sh
# Build and publish a LeanLink release (maintainers only).
#
# Usage: sh tools/release.sh [--publish] [--repo OWNER/REPO] [--notes TEXT]
#
#   1. builds both models (stock OTAs must be in stock/, see docs/BUILDING.md);
#   2. copies the images as leanlink-<model>-<YYMMDDHH>-LL.img into build/release/, together with
#      flasher.html, flash.sh and flash_windows.bat;
#   3. with --publish only: creates the GitHub release <YYMMDDHH>-LL with these files attached
#      (needs `gh auth login`).
#   A guard refuses anything except those files; vendor stock images and --debug images are never published.
#
# Without --publish nothing is created; the script prepares build/release/ and prints what it would do.

set -eu

PUBLISH=0
REPO=lachyn/leanlink
NOTES=""
while [ $# -gt 0 ]; do
    case "$1" in
        --publish) PUBLISH=1 ;;
        --repo) REPO=$2; shift ;;
        --notes) NOTES=$2; shift ;;
        -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
OUT="$ROOT/build/release"

run() {  # print, and execute only with --publish
    echo "+ $*"
    if [ "$PUBLISH" = 1 ]; then "$@"; fi
}

# 1. Build
python3 tools/build_patched_ota.py --model all --repo "$REPO"

# Versions from the builder (appver "26122204.5140.2.LL" -> "26122204")
VERS=$(python3 -c '
import sys; sys.path.insert(0, "tools")
from build_patched_ota import PROFILES
for p in PROFILES.values():
    print(p.model_id, p.patched_appver, p.out_relpath)')
VER=$(echo "$VERS" | awk '{split($2, a, "."); print a[1]}' | sort -u)
[ "$(echo "$VER" | wc -l)" -eq 1 ] || { echo "models have different version dates: $VER" >&2; exit 1; }
TAG="$VER-LL"
: "${NOTES:=LeanLink $TAG}"

# 2. Release files
rm -rf "$OUT"
mkdir -p "$OUT"
echo "$VERS" | while read -r model appver out; do
    name="leanlink-$model-$VER-LL.img"
    cp "$out" "$OUT/$name"
    echo "image  $OUT/$name  ($appver)"
done
cp flasher.html flash.sh flash_windows.bat "$OUT/"

# Guard: only LeanLink release images and the three flashing tools, never a vendor stock or debug image.
python3 - "$OUT" <<'EOF'
import hashlib, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools")
import leanlink_ota as lo
out = Path(sys.argv[1])
stock = {hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("stock").glob("*.img")}
bad = []
for f in sorted(p for p in out.rglob("*") if p.is_file()):
    rel = f.relative_to(out).as_posix()
    if rel in ("flasher.html", "flash.sh", "flash_windows.bat"):
        continue
    if not re.fullmatch(r"leanlink-(6071|5140)-\d{8}-LL\.img", rel):
        bad.append(f"{rel}: only leanlink-<model>-<YYMMDDHH>-LL.img and the flashing tools are allowed")
        continue
    data = f.read_bytes()
    if hashlib.sha256(data).hexdigest() in stock:
        bad.append(f"{rel}: identical to a vendor stock image")
        continue
    arc = lo.CpioArchive.parse(lo.unwrap_envelope(lo.decrypt(data)))
    with tempfile.NamedTemporaryFile(suffix=".sqfs") as t:
        t.write(arc.member("customer"))
        t.flush()
        sysjson = subprocess.run(["unsquashfs", "-cat", t.name, "app/system.json"],
                                 capture_output=True, text=True).stdout
        start = subprocess.run(["unsquashfs", "-cat", t.name, "app/lyLink.sh"],
                               capture_output=True, text=True).stdout
    if re.search(r'"appver":\s*"[^"]*-debug"', sysjson) or "/tmp/dbg" in start or not start:
        bad.append(f"{rel}: debug image (root shell without password), never publish it")
    elif not re.search(r'"appver":\s*"[0-9.]+\.LL"', sysjson):
        bad.append(f"{rel}: not a LeanLink build (appver does not end with .LL)")
if bad:
    sys.exit("refusing to publish:\n  " + "\n  ".join(bad))
print("guard ok: only LeanLink images and the flashing tools")
EOF

SUMS=$(cd "$OUT" && sha256sum leanlink-*-"$VER"-LL.img)
RELNOTES=$(printf '%s\n\nSHA-256:\n```\n%s\n```\n' "$NOTES" "$SUMS")
echo
echo "Release $TAG for $REPO"
ls -l "$OUT"

# 3. Publish
[ "$PUBLISH" = 1 ] || echo "Dry run: the following command runs only with --publish"
# shellcheck disable=SC2046
run gh release create "$TAG" --repo "$REPO" --title "LeanLink $TAG" --notes "$RELNOTES" $(ls "$OUT"/*)
