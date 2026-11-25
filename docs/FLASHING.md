# Installing LeanLink

LeanLink is installed like an official update: you upload one file to the adapter over the adapter's own
Wi-Fi. No cables, no opening the case, no drivers. The same way takes you back to the stock firmware.

## Contents

- [1. Which image do I need?](#1-which-image-do-i-need)
- [2. Install step by step](#2-install-step-by-step)
- [3. Tools per device](#3-tools-per-device)
  - [Browser (any device)](#browser-any-device)
  - [Windows script](#windows-script)
  - [macOS and Linux script](#macos-and-linux-script)
  - [Android without a browser (Termux, ADB)](#android-without-a-browser-termux-adb)
- [When the page does not open](#when-the-page-does-not-open)
- [Updating LeanLink later](#updating-leanlink-later)
- [Going back to stock](#going-back-to-stock)
- [Recovery](#recovery)
- [Useful addresses](#useful-addresses)

## 1. Which image do I need?

The **project ID** decides, not the name on the box. Join the adapter's Wi-Fi (`CAR2-xxxx` on stock firmware,
`LeanLink-xxxx` with LeanLink; password `88888888`, on some units `12345678`), open <http://192.168.1.101/> and
look at *Build Number*:

| Build Number ends with | Retail product | Image to download |
|---|---|---|
| `.6071.2` | Ottocast Mini Pico | `leanlink-6071-<version>-LL.img` |
| `.5140.2` | Ottocast Mini Cube 3.0 | `leanlink-5140-<version>-LL.img` |

Download it from the [latest release](https://github.com/lachyn/leanlink/releases/latest). The two images are
**not interchangeable**; every tool checks the model before uploading. Keep the file name as it is.

## 2. Install step by step

The adapter's Wi-Fi has **no internet**. So first download everything you need, then connect to the adapter.

1. **Download while you have internet:** the image for your model and, if the adapter still runs the stock
   firmware, also [`flasher.html`](../flasher.html) (on the release page or in this repository).
2. **Power:** plug the adapter into a USB port that stays powered for the next 3 minutes (PC, USB charger,
   car with the ignition on).
3. **Free the adapter:** on a phone that uses the adapter for Android Auto / CarPlay, switch **Bluetooth off**
   and wait about 30 s. While a phone projects, it cannot open the adapter's page. A laptop or a second phone
   does not need this.
4. **Connect:** join the adapter's Wi-Fi. When the device says the network has no internet, choose
   **stay connected**. Then switch **mobile data off** (on a laptop: unplug the network cable), otherwise the
   device sends the upload to the internet instead of to the adapter.
5. **Upload:**
   - adapter with **LeanLink**: open <http://192.168.1.101/>, section *Firmware update*, pick the file and
     press *Upload and install*;
   - adapter with **stock firmware**: open `flasher.html` in the browser (Chrome, Edge, Firefox or Safari; not
     inside a WhatsApp / Messenger preview), pick the file and press *Upload*. The stock settings page has no
     file upload.

   Or use a script instead of the browser, see [Tools per device](#3-tools-per-device).
6. **Wait about 2 minutes and do not unplug:**

   | Step | Time | What you see |
   |---|---|---|
   | Upload | 5–30 s | progress bar, or `{"code": 0, "msg": "upload successful"}` |
   | Writing | ~75 s | LED blinks |
   | Restart | ~30 s | Wi-Fi disappears and comes back as `LeanLink-xxxx` |

   From stock firmware with `flasher.html`, the adapter does not restart by itself: when the *status* link shows
   `"update": 3` (LED white), press *Set 5 GHz channel 36* and then *Reboot*. The scripts do this for you.
7. **Check:** join `LeanLink-xxxx` again and open <http://192.168.1.101/>. *Build Number* ends with `.LL`.
8. **First install from stock only:** tap *Restore factory settings* → *Forget phones*. It removes old
   Bluetooth pairings, which on stock firmware can make the Bluetooth chip restart again and again.
9. **Done:** switch mobile data and Bluetooth back on. Plug the adapter into the car and start the car; once the
   car starts Android Auto the adapter shows up as `LeanLink-xxxx` and you pair the phone with it (in Android
   Auto mode its Bluetooth stays off until then, so pairing on a charger does not work).

## 3. Tools per device

### Browser (any device)

Steps 1–9 above. Works on Android, iPhone, Windows, macOS and Linux.

- **Android:** open `flasher.html` from the Files app in Chrome.
- **iPhone / iPad:** save the files to *Files*; if Files only shows a preview of `flasher.html`, use
  Share → Open in Safari. Not tested on our side yet; reports welcome.

### Windows script

`flash_windows.bat` uploads, waits for the write, sets 5 GHz channel 36 and restarts the adapter.
It needs `curl.exe`, which is built into Windows 10 1803 and later.

1. Put `flash_windows.bat` and the image into one folder.
2. Join the adapter's Wi-Fi and unplug the network cable.
3. Double-click `flash_windows.bat`. It finds the adapter and checks the model.

### macOS and Linux script

`flash.sh` does the same as the Windows script; `-r` also restores factory settings (*Forget phones*) at the
end, which is recommended for the first install from stock.

```bash
# Linux: join the Wi-Fi from the terminal (or from the desktop)
nmcli dev wifi connect LeanLink-xxxx password 88888888    # the real name of your adapter, CAR2-xxxx on stock

sh flash.sh -r leanlink-5140-<version>-LL.img             # ly5140
sh flash.sh -r leanlink-6071-<version>-LL.img             # ly6071
```

On a Mac with a network cable plugged in, add `-I en0` (the Wi-Fi interface, check with
`networksetup -listallhardwareports`).

```text
sh flash.sh [-i IP] [-I IFACE] [-c CHANNEL] [-r] [-f] <update.img>
  -i IP       adapter address (default: found automatically)
  -I IFACE    send traffic only through this interface (wlan0 on Android, en0 on a Mac)
  -c CHANNEL  Wi-Fi channel to set after flashing (default 36; 0 = leave unchanged)
  -r          restore factory settings (forget phones) after flashing
  -f          skip the file-name vs. model check (needed for stock images)
```

The script reads the adapter's project ID and refuses an image whose file name is for the other model.

### Android without a browser (Termux, ADB)

With `-I wlan0` the traffic stays on Wi-Fi, so mobile data can stay on.

```bash
# Termux on the phone
pkg install curl
termux-setup-storage
sh ~/storage/downloads/flash.sh -I wlan0 -r ~/storage/downloads/leanlink-5140-<version>-LL.img

# From a PC over USB (USB debugging on); the phone is joined to the adapter's Wi-Fi
adb push flash.sh leanlink-5140-<version>-LL.img /data/local/tmp/
adb shell sh /data/local/tmp/flash.sh -I wlan0 -r /data/local/tmp/leanlink-5140-<version>-LL.img
```

## When the page does not open

- **The phone runs Android Auto / CarPlay through the adapter:** it keeps the adapter's Wi-Fi to itself
  (Chrome shows `ERR_INTERNET_DISCONNECTED`). Switch Bluetooth off, wait 30 s, join the Wi-Fi again.
- **Mobile data or a network cable is on:** switch it off; the device sends the request there.
- **The Wi-Fi is not visible:** your device may not support the adapter's channel (a PC with 2.4 GHz-only
  Wi-Fi does not see channel 36). Use a phone, or switch the adapter to channel 6 on its settings page.
- **Linux shows "Unable to open folder" pop-ups:** the adapter presents itself as a media device for a moment
  while it waits for a phone. Disable automount of removable media.

## Updating LeanLink later

Same as steps 1–7: download the new image, connect to `LeanLink-xxxx`, *Firmware update* → pick the file →
*Upload and install*. The page links to the newest release and checks the file before sending it (complete,
checksum correct, right model). Settings and pairings stay; no factory reset needed.

## Going back to stock

Download the stock image of your model from the vendor (links in
[BUILDING.md](BUILDING.md#1-get-the-stock-firmware)) and upload it like a LeanLink image: LeanLink's
*Firmware update* accepts it, `flash.sh` needs `-f` (the vendor file name does not say the model). Afterwards
*Restore factory settings*; the Wi-Fi is called `CAR2-xxxx` again.

## Recovery

- **LED blinks and the car shows nothing:** the adapter is waiting for a phone. Switch Bluetooth on on the
  paired phone, or pair one (Bluetooth name `LeanLink-xxxx`). In Android Auto mode the adapter's Bluetooth
  appears only once the car has started Android Auto (ignition on, adapter in the car's USB port), not on a
  charger.
- **Projection fails although the phone is on the adapter's Wi-Fi:** if you saved the adapter's Wi-Fi on the
  phone (for the settings page), the phone may join that saved network instead of the one Android Auto creates.
  Delete the saved network or switch its auto-reconnect off; join it only to open the settings page.
- **`UNKNOWN` car or duplicate cars in the phone's Android Auto list:** left over from older firmware. Remove
  them in Android Auto → *Previously connected cars* and connect again.
- **A phone does not pair or reconnect:** *Restore factory settings* → *Forget phones*, then pair again.
- **Adapter does not start (no Wi-Fi, nothing in the car):** an update writes only the kernel and the
  application; the bootloader and the recovery system stay intact, so an interrupted write can be repeated.
  Power it from a PC, wait two minutes and upload again once its Wi-Fi appears. If it never appears, open an
  issue and describe what you see; the last resort (Allwinner USB recovery with the vendor's full flash image)
  needs tools that are not part of LeanLink.

## Useful addresses

| Address | Effect |
|---|---|
| <http://192.168.1.101/> | Settings page |
| `/cgi-bin/index.cgi?id=host` | Status (`appver` = version, `update` = 3 when an update is written, `sig` = Wi-Fi channel) |
| `/cgi-bin/index.cgi?id=set&wifi=36` | Set the Wi-Fi channel (1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161) |
| `/cgi-bin/index.cgi?id=set&rst=1` | Restore factory settings: forget phones and the AA / CarPlay mode, restart |
| `/cgi-bin/index.cgi?id=set&rst=2` | Restore everything: also the settings on the page, restart |
| `/cgi-bin/index.cgi?id=set&conn=aoa` | Restart the adapter (keeps the AA / CarPlay mode) |
