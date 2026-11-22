# Settings

Join the adapter's Wi-Fi (`LeanLink-xxxx`, password `88888888`) and open <http://192.168.1.101/>.
Tap a setting to change it; LeanLink tells you what the chosen value does and asks before applying it.
**Most changes restart the adapter** (about 20 s); a connected phone reconnects by itself.

The vendor never documented these options. What follows comes from reading the firmware's own programs. Each
setting says how sure we are:

- **verified**: tried on a real adapter;
- **high**: the code path is clear, not every value was tried in a car;
- **medium / low**: partly inferred, because the CarPlay part of the firmware is encrypted and could not be read.

Settings are stored in a separate settings area of the flash and survive updates.

Some options appear only on some models (the page hides what your model does not support).

---

## Contents

- [Overview](#overview)
- [Wi-Fi channel](#wi-fi-channel)
- [Status LED](#status-led)
- [Start-up delay](#start-up-delay)
- [CarPlay video mode](#carplay-video-mode)
- [CarPlay audio after calls](#carplay-audio-after-calls)
- [CarPlay GPS source](#carplay-gps-source)
- [Android Auto certificate](#android-auto-certificate)
- [Unit Type](#unit-type)
- [Restore factory settings](#restore-factory-settings)
- [Android Auto or CarPlay?](#android-auto-or-carplay)
- [Firmware update](#firmware-update)
- [Problem report](#problem-report)

## Overview

| Setting | Values | Use it when |
|---|---|---|
| Wi-Fi channel | 36 (default), 6, 149, 161 | The phone connection drops, or your device cannot see 5 GHz |
| Status LED | On, Off | The light bothers you at night |
| Start-up delay | Off, 15 s, 30 s | The car misses the adapter after starting the engine |
| CarPlay video mode | Standard, Compatibility | The CarPlay picture is black, frozen or distorted |
| CarPlay audio after calls | Standard, Re-sync after calls | CarPlay music stays silent after a phone call |
| CarPlay GPS source | Car GPS, Phone GPS only | The position in CarPlay maps jumps |
| Android Auto certificate | Cloud (default), Built-in | Android Auto stops starting |
| Unit Type | Default, Ford SYNC 2.0 | Only for a Ford SYNC 2.0 head unit with CarPlay |
| Restore factory settings | | Pairing problems; after the first install |

## Wi-Fi channel

Channel of the adapter's own Wi-Fi, which the phone uses for Android Auto / CarPlay.

| Value | What it does |
|---|---|
| **36 · 5 GHz** (LeanLink default) | Fast, allowed indoors and in cars all over Europe. Best choice for most people. |
| 6 · 2.4 GHz | Slower but reaches further and works with older phones and PCs without 5 GHz. |
| 149 · 5 GHz | The stock default. Fine in the USA and Asia; outside the common European band. |
| 161 · 5 GHz | Alternative upper 5 GHz channel (USA / Asia). |

**Change it when** the phone keeps dropping off the adapter's Wi-Fi, when there is interference on channel 36,
or temporarily when a device you want to use for installing cannot see 5 GHz.
The adapter restarts when the channel changes. Confidence: **verified**.

Other channels (1, 11, 40, 44, 48, 153, 157) can be set through
`http://192.168.1.101/cgi-bin/index.cgi?id=set&wifi=<channel>`.

## Status LED

| Value | What it does |
|---|---|
| **On** (default) | The LED shows the connection state. |
| Off | The LED stays dark. |

**Change it when** the light is distracting at night. A long press of the button on the adapter (where there is
one) toggles the same setting. Confidence: **verified**.

## Start-up delay

Waits before the adapter starts Bluetooth, Wi-Fi and its USB connection to the car.

| Value | What it does |
|---|---|
| **Off** (default, recommended) | Starts as soon as it has power. |
| 15 s | Starts 15 s after power-on. |
| 30 s | Starts 30 s after power-on. |

**Change it when** the car's head unit boots slowly and does not notice the adapter after you start the engine.
Confidence: **high** for Android Auto (the delay is in the Android Auto service); **medium** for CarPlay (very
likely the same, not visible in the code).

## CarPlay video mode

Only affects CarPlay; Android Auto video is passed through unchanged.

| Value | What it does |
|---|---|
| **Standard** (default) | Normal CarPlay video. |
| Compatibility | The vendor's alternative CarPlay video handling for head units that show a black, frozen or distorted picture. |

**Change it when** the CarPlay picture is broken on your head unit. What exactly changes is inside the vendor's
encrypted CarPlay module. Confidence: **high** that Android Auto ignores it (from the code); **low** for CarPlay (effect
not visible in the code).

## CarPlay audio after calls

Only affects CarPlay; no effect on Android Auto.

| Value | What it does |
|---|---|
| **Standard** (default) | Normal CarPlay audio handling. |
| Re-sync after calls | When a phone call ends, the adapter takes the car's main audio channel back once. |

**Change it when** music or navigation stays silent after a phone call in CarPlay. Confidence: **medium-high**.
(The vendor page also offered two more values that no part of the firmware we could read uses; LeanLink does
not show them.)

## CarPlay GPS source

Only affects CarPlay. Android Auto always uses the car's GPS when the car provides one.

| Value | What it does |
|---|---|
| **Car GPS** (default) | CarPlay may use the car's GPS signal. |
| Phone GPS only | The car's location data is not passed on; the iPhone uses its own GPS. |

**Change it when** your position jumps around in CarPlay maps (a weak or wrong GPS signal from the car).
Confidence: **low-medium**: the switch exists in the CarPlay library, but which value turns it on is inferred
from the code, not tested in a car.

## Android Auto certificate

The certificate the adapter presents to the phone when Android Auto starts.

| Value | What it does |
|---|---|
| **Cloud** (default) | Uses the vendor's certificate stored on the adapter (normal operation). "Cloud" is the vendor's name for it; no internet is needed. |
| Built-in | Uses the reference certificate built into the firmware (valid until 2044). |

**Change it when** Android Auto suddenly stops starting on every phone. Switch back to *Cloud* if *Built-in*
does not help. The stored certificate's expiry date (December 2026) does not matter: we tested with the head
unit's and the phone's clocks set to 2027 and Android Auto still started. Confidence: **medium-high**.

## Unit Type

| Value | What it does |
|---|---|
| **Default (For Most CarPlay Units)** | Normal behaviour. |
| Ford SYNC 2.0 Specific | Vendor adjustments for Ford SYNC 2.0 head units. |

**Change it when** you have a Ford with SYNC 2.0 and CarPlay misbehaves. The adjustments live in the vendor's
encrypted CarPlay module; we could not see what they do. Confidence: **low** (effect unknown).

## Restore factory settings

Tapping the row offers two choices; LeanLink stays installed with both, and the next start is in Android Auto
mode (an iPhone switches the adapter to CarPlay by itself). Pair your phone again afterwards.

| Choice | Request | What it clears |
|---|---|---|
| **Forget phones** | `id=set&rst=1` | Paired phones and the stored Android Auto / CarPlay mode; the settings on this page stay |
| **Everything** | `id=set&rst=2` | Everything the adapter stores in `/mnt/UDISK` (`rm -rf`): also the settings on this page |

*Forget phones* is enough for pairing problems. Confidence: **verified** for *Forget phones*, **medium** for
*Everything* (taken from the firmware code, not tried in a car).

**Use it** after the first installation from stock firmware, when a phone no longer pairs or reconnects, or
before giving the adapter to someone else (then choose *Everything*).

---

## Android Auto or CarPlay?

There is no setting for this: the adapter decides by itself.

- After installation or a factory reset it starts in **Android Auto** mode.
- When an **iPhone** connects, the vendor software switches to CarPlay (the adapter restarts once).
- When an **Android phone** asks for Android Auto while the adapter is in CarPlay mode and no iPhone is
  connected, LeanLink switches back to Android Auto (not within the first 25 s after power-on, so a passenger's
  phone cannot kick out an iPhone that is still reconnecting).
- There is no reliable "force mode" request: `id=set&conn=aoa` / `conn=cp` only store the text and restart the
  adapter, the mode stays as it was. To go back to Android Auto, switch off Bluetooth on the iPhone and connect
  the Android phone.

## Firmware update

Shows the installed version and a link to the newest LeanLink release. Download the image while you have
internet, then pick it here: the page checks that it is complete, has a valid checksum and is for this
model before uploading it. Stock vendor images are accepted too, which is how you go back to stock.

Vendor online updates are disabled because they would replace LeanLink with the stock firmware without asking.

## Problem report

Fill in the car make, model, year and a description, then *Save problem report*. The adapter's status and system
log are saved as a text file on your device, with the serial number, MAC addresses and paired phone names
masked. The page then offers a pre-filled GitHub issue to which you attach the file. Nothing is sent to the
vendor or anywhere else automatically.

The system log can also be downloaded by hand from `http://192.168.1.101/cgi-bin/index.cgi?id=logcat` and
decoded with `python3 tools/decode_logcat.py log.gz log.txt`.
