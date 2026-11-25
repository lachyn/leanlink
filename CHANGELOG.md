# Changelog

Release images and checksums: <https://github.com/lachyn/leanlink/releases>. Versions are the build number the
adapter shows (*Build Number* `<version>.<project>.2.LL`).

## 26122221-LL

- **Phone no longer connects before the car is ready.** In Android Auto mode the adapter's Bluetooth starts only
  when the car starts Android Auto (ignition on). Before, the phone connected as soon as the adapter had power
  (car off, after-run, charger), the session ended after 10 s, the Android Auto service crashed and the phone
  could keep an `UNKNOWN` car or duplicate cars in its list. Projection now starts 7 to 9 s after the car asks
  for Android Auto. Pair a new phone in the car, not on a charger. CarPlay mode is unchanged.
- USB watchdog merged into the same loop; it re-binds USB only when a USB function is configured (no more
  failed re-bind at boot).
- Docs: how to pair after the change, saved Wi-Fi network on the phone blocking projection, removing old
  `UNKNOWN` cars.

## 26122220-LL

- Settings page: words are no longer split across lines in dialogs; Czech, Slovak and Polish texts keep
  one-letter prepositions and number + unit together.

## 26122219-LL

- Clearer installation guide.
- The settings page no longer checks for updates online (a phone has no internet on the adapter's Wi-Fi); it
  links to the newest release.
- Options are a tap list; factory reset offers *Forget phones* / *Everything*.
- The release includes `flasher.html`, `flash.sh` and `flash_windows.bat`.
