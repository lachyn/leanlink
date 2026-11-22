<p align="center"><img src="docs/assets/logo.svg" width="96" height="96" alt="LeanLink logo"></p>

<h1 align="center">LeanLink</h1>

<p align="center"><b>Wireless Android Auto &amp; CarPlay · debloated</b><br>
A fixed and slimmed-down firmware for cheap wireless Android Auto / CarPlay USB adapters.</p>

---

## Contents

- [What it is](#what-it-is)
- [Why](#why)
- [Who it is for](#who-it-is-for)
- [How to install](#how-to-install)
- [Documentation](#documentation)
- [License and credits](#license-and-credits)

## What it is

LeanLink is a repaired version of the firmware that ships on several low-cost wireless Android Auto and CarPlay
adapters (the small USB dongles that make a wired car system wireless). It keeps the vendor's own Android Auto and
CarPlay programs and only changes how they are started, plus the settings page and the start-up screens. It
installs like an official update, over the adapter's own Wi-Fi, and you can go back to the stock firmware the
same way.

## Why

On the stock firmware these adapters:

- drop the phone every few seconds;
- leave the car's USB port dead until you unplug the adapter;
- start in CarPlay after a reset or an update, so Android-only cars never see Android Auto;
- stay in CarPlay once an iPhone has used them and ignore Android phones;
- waste the radio on features nobody needs (a phone app link that scans all the time, Huawei HiCar);
- have a settings page with unexplained "Mode 1 / Mode 2" options and vendor cloud updates that would silently
  put the stock firmware back.

LeanLink fixes all of that. It switches between Android Auto and CarPlay by itself, names the adapter
`LeanLink-xxxx`, explains every setting, checks update files before installing them and saves problem reports
locally instead of sending them anywhere. Details: [How it works](docs/HOW-IT-WORKS.md).

## Who it is for

Owners of these adapters (the **project ID decides, not the name on the box**):

| Retail product | Project ID | Stock firmware tested |
|---|---|---|
| Ottocast Mini Pico (`CA525-T`) | `ly6071` | `26101215.6071.2` |
| Ottocast Mini Cube 3.0 (`CP88-T`) | `ly5140` | `26101218.5140.2` |

Other adapters that report project `ly6071` or `ly5140` should work too. To find yours: power the adapter from
USB, join its Wi-Fi (`CAR2-xxxx`, password `88888888`), open <http://192.168.1.101/> and look at
*Build Number*: it ends with `.6071.2` or `.5140.2`. The two images are not interchangeable; every tool checks
the model.

## How to install

1. While you have internet, download the image for your project ID (`leanlink-6071-…` or `leanlink-5140-…`)
   from the [latest release](https://github.com/lachyn/leanlink/releases/latest), and `flasher.html` if the
   adapter still runs the stock firmware. The adapter's Wi-Fi has no internet.
2. Plug the adapter into a USB port that stays powered.
3. On the phone: switch Bluetooth off (so Android Auto / CarPlay let go of the adapter), join the adapter's
   Wi-Fi (password `88888888`), stay connected although it has no internet, and switch mobile data off.
4. Upload the image: from stock with `flasher.html` (or the scripts), from LeanLink on <http://192.168.1.101/>
   → *Firmware update*. Wait about 2 minutes and do not unplug.
5. After the first install from stock: *Restore factory settings* → *Forget phones*, then pair your phone again.

All steps, scripts for Windows, macOS and Linux, and how to go back to stock:
[Installing LeanLink](docs/FLASHING.md).

## Documentation

- [Installing LeanLink](docs/FLASHING.md): all platforms, going back to stock, recovery
- [Settings](docs/SETTINGS.md): every option on the adapter's page, what it does and when to change it
- [How it works](docs/HOW-IT-WORKS.md): what LeanLink fixes and adds, boot flow, the evidence for each bug
- [Building](docs/BUILDING.md): build the image yourself, verify a release, repository layout, debugging

## License and credits

LeanLink's own code and documentation are released under the [MIT License](LICENSE). The vendor's firmware is
not covered by it, and the stock update images are never published here. The splash screens in
`tools/branding/png/` are re-coloured versions of the vendor's start-up screens. The update format of this platform was
first documented by the **CatPlay** project; `tools/leanlink_ota.py` is an independent implementation.

LeanLink is an independent project, **not affiliated with, endorsed by or supported by** Shenzhen LiaoYuan,
Ottocast, Google or Apple. "Android Auto" is a trademark of Google LLC, "CarPlay" is a trademark of Apple Inc.
LeanLink release images contain the vendor's binaries unmodified, as shipped in the vendor's public update, with
LeanLink's changes applied. Installing modified firmware is at your own risk.
