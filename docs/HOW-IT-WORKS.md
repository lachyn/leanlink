# How LeanLink works

## Contents

- [What LeanLink changes](#what-leanlink-changes)
- [The hardware and the stock firmware](#the-hardware-and-the-stock-firmware)
- [Boot flow](#boot-flow)
- [Files LeanLink replaces](#files-leanlink-replaces)
- [Bugs fixed, with the evidence](#bugs-fixed-with-the-evidence)
- [What LeanLink does not change](#what-leanlink-does-not-change)
- [Credits](#credits)

## What LeanLink changes

### Fixes

| Problem on stock firmware | What you notice | LeanLink |
|---|---|---|
| The Android Auto service crashes after the USB mode switch and never re-attaches USB | Car's USB port dead until you unplug the adapter | A small watchdog re-attaches USB after about 9 s |
| The Wi-Fi setup writes its DHCP config to a different file than the Android Auto service reads | Phone disconnects from the adapter every ~12 s | Config written where it is read |
| Two extras nobody here uses run all the time: a Bluetooth link for the vendor's phone app (Ottopilot) that scans every 5 s, and a second Wi-Fi network for Huawei HiCar | Pairing failures; the shared radio and the little memory are partly wasted | Both removed; the radio serves only your phone's connection |
| After a factory reset the adapter starts in CarPlay mode | Android-only cars never see Android Auto | First start after install or reset is Android Auto; iPhones still switch it to CarPlay automatically |
| Once an iPhone has used the adapter, it stays in CarPlay mode and ignores Android phones | An Android phone connected later never gets Android Auto, only a factory reset helps | When an Android phone asks for Android Auto and no iPhone is connected, the adapter switches to Android Auto by itself (it restarts once, ~20 s) |
| Default Wi-Fi channel 149 (US / China band) | Weak or no link with some phones in Europe | Default channel 36 |

### Additions

- **Own name:** the adapter's Wi-Fi and Bluetooth are called `LeanLink-xxxx` (the suffix stays per unit).
- **Settings page you can understand:** every option on <http://192.168.1.101/> has a plain-English label,
  an explanation and a confirmation before the adapter restarts. See [Settings](SETTINGS.md).
- **Safe local updates:** vendor online updates are switched off (they would silently put the stock firmware
  back). You upload a firmware file instead; the page checks in the browser that the file is complete, has the
  right checksum and is for this model before sending it.
- **No online check:** a phone has no internet on the adapter's Wi-Fi, so the page only links to the newest
  release; you download the file first and pick it afterwards.
- **Private problem reports:** *Save problem report* downloads the adapter's status and system log to your
  device with the serial number, MAC addresses and phone names masked, and then offers a link to a pre-filled
  GitHub issue to which you attach the file. Nothing is sent anywhere automatically.
- **LeanLink splash screens** on the car display (re-coloured versions of the vendor's screens with the LeanLink logo).

### Disabled on purpose

The Bluetooth link for the vendor's phone app (Ottopilot), support for the vendor's Bluetooth remote button
(BT04), Huawei HiCar, and vendor online updates.

## The hardware and the stock firmware

The adapters are built around an Allwinner V821B (one RISC-V core, 64 MB RAM, 16 MB SPI flash) running the
vendor's Tina Linux. The flash holds a bootloader, a kernel, a recovery kernel, a read-only root filesystem and a
small `customer` SquashFS (mounted at `/mnt/customer`) with the application: shell start scripts plus the
vendor's closed programs (`raaservice` for Android Auto, `rcpservice` / `lylinkapp` for CarPlay, `btapp` for
Bluetooth, `lyhostapd` for Wi-Fi, a busybox web server with the settings page).

An official update (`update.img`) is an encrypted SWUpdate archive that rewrites only `boot` (kernel) and
`customer`:

```text
update.img = XOR( "<md5>  update.swu\n" + update.swu , 256-byte key )
update.swu = CPIO (newc with checksums): sw-description, customer (SquashFS), kernel
```

LeanLink takes the vendor's own update, changes files inside `customer` and packs it again in exactly the same
format, so the adapter installs it like any vendor update. The kernel, bootloader, recovery and all vendor
programs stay byte-for-byte the vendor's.

## Boot flow

```text
init → /mnt/customer/app/lyLink.sh
         ├─ /mnt/UDISK/ly_linktype_aa present → Android Auto mode
         │     ├─ lyLoadModule.sh &   Wi-Fi access point (lyhostapd) + DHCP (udhcpd), then blink.sh
         │     └─ raaservice          Android Auto relay: Bluetooth hand-over, Wi-Fi, USB to the car
         └─ otherwise → CarPlay mode (mdnsd, rcpservice, lylinkapp)
blink.sh → btapp (Bluetooth stack)
```

`raaservice` acts as a phone towards the car (USB, first as a media device `2717:ff40`, then as an Android
accessory `18d1:2d00`) and as a head unit towards the phone (Bluetooth to hand over the Wi-Fi credentials, then
TCP over Wi-Fi). Video resolution and frame rate are negotiated between car and phone; the adapter only
forwards the stream.

## Files LeanLink replaces

| File in `customer` | Why |
|---|---|
| `app/lyLink.sh` | Android Auto default after a reset, USB watchdog, CarPlay → Android Auto switch, honour `force_raa` (`id=set&aa=2`) in CarPlay mode, free RAM in Android Auto mode, keep the mode across updates, restart after an update, `LeanLink-xxxx` name |
| `app/lyLoadModule.sh` | DHCP config at the path `raaservice` reads, channel 36 default, no HiCar Wi-Fi Direct group |
| `app/blink.sh` | Start only the Bluetooth stack (no extra BLE advertising) |
| `app/otto_goc` | Replaced by a two-line stub (Ottopilot BLE daemon off) |
| `app/system.json` | LeanLink version string (`….LL`), LED pin per model |
| `ota/www/index.html`, `ota/www/js/cpbox.js` | LeanLink settings page: labels and help, verified local upload, link to the newest release, private problem report, vendor online update off |
| `app/logo/*.png` | Splash screens on the car display (`tools/branding/png/`) |

All script changes are inline in [`tools/build_patched_ota.py`](../tools/build_patched_ota.py); the web UI
additions are in [`tools/webui/leanlink.js`](../tools/webui/leanlink.js).

## Bugs fixed, with the evidence

1. **Phone dropped every ~12 s.** The stock script copies the DHCP config to `/tmp/udhcpd_ap.conf`, but
   `raaservice` reads `/tmp/udhcpd.conf` and disconnects the phone when it is missing. System log:
   `E lyraa : src/wpa.c:1180 udhcpd() read /tmp/udhcpd.conf fail`.
2. **Dead USB port.** When switching from media device to Android accessory, `raaservice` unbinds the USB
   gadget; if it then crashes, the restarted instance never binds it again. Kernel log:
   `raaservice[219]: unhandled signal 11 ... in liblylinkmw.so.1`, with
   `/sys/kernel/config/usb_gadget/g1/UDC` left empty. LeanLink re-binds `44100000.udc-controller` when it stays
   empty for about 9 s.
3. **Pairing failures and wasted airtime.** `blink.sh` sends `AT#LR` and starts `otto_goc`, which advertises a
   second Bluetooth LE identity (for the Ottocast phone app and a BT04 remote) and scans for 15 s every 5 s;
   phones occasionally failed with `HCI_ERR_PAGE_TIMEOUT`. `lyLoadModule.sh` also runs a Huawei HiCar Wi-Fi
   Direct group (`DIRECT-xx`) on the same single radio. After the change the status page shows no second
   Bluetooth address and no `DIRECT-xx` network.
4. **CarPlay-only after a factory reset.** The mode depends on the file `/mnt/UDISK/ly_linktype_aa`, which a
   reset deletes; the adapter then enumerates as an Apple device (`05ac:12a8`) and an Android-only car never
   sees Android Auto. LeanLink creates the file on the first start after installation or reset.
5. **Android phones locked out in CarPlay mode.** In CarPlay mode `btapp` reports an Android phone asking for
   Android Auto as `AA` on `/dev/rf_serial`, but no stock process reads it. LeanLink switches to Android Auto
   when this happens, no iPhone is connected over Wi-Fi and the adapter has been up for at least 25 s.
6. **Hidden "force Android Auto" ignored in CarPlay mode.** The stock setting `id=set&aa=2` (not offered on the
   LeanLink page) only creates `/mnt/UDISK/force_raa`, which the stock script reads in Android Auto mode only.
   LeanLink honours it in both modes.
7. **Weak Wi-Fi in Europe.** The stock default channel is 149 (5745 MHz), outside the common European band.
   LeanLink defaults to channel 36 when no channel was chosen.
8. **Stale pairings resetting the Bluetooth chip.** A pairing with a phone that is no longer around made `btapp`
   retry every ~57 s and reset the Bluetooth chip each time. A factory reset after installation (`flash.sh -r`)
   clears it.
9. **Every update ended in CarPlay mode.** The stock start script deletes `/mnt/UDISK/ly_linktype_aa` while an
   update is installed, so the adapter came back in CarPlay mode. LeanLink leaves the file alone.
10. **Stuck after an update until unplugged.** The vendor updater only reports "done" (`update=3`, white LED)
   and waits for someone to restart the adapter; a phone that lost the adapter's Wi-Fi during the update cannot.
   LeanLink restarts by itself about 10 s after a write it saw during the same start (never because of a "done"
   state left over at boot).

## What LeanLink does not change

- Video quality: resolution, frame rate and codec are chosen by the car and the phone.
- Wi-Fi speed on `ly5140`: its Realtek driver supports 802.11n only (HT40, up to 150 Mbit/s); Android Auto needs
  a few Mbit/s.
- The vendor's Android Auto and CarPlay programs, kernel and bootloader.
- LED colours and brightness: the LED is RGB, but `raaservice` sets fixed colours per state; writing other values
  to the LED driver had no visible effect.

## Credits

The OTA encryption key and the update layout were first documented by the CatPlay project.
`tools/leanlink_ota.py` is LeanLink's own implementation of that format.
