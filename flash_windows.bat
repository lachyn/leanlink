@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ====================================================================
echo   LeanLink (ly6071 / ly5140) - Windows flasher
echo ====================================================================
echo.

set "BOX_IP="
for %%I in (192.168.1.101 192.168.43.1 192.168.50.2) do (
    if not defined BOX_IP (
        curl.exe -s --max-time 3 "http://%%I/cgi-bin/index.cgi?id=host" > "%TEMP%\car2_host.json" 2>nul
        findstr /C:"appver" "%TEMP%\car2_host.json" >nul 2>nul
        if not errorlevel 1 set "BOX_IP=%%I"
    )
)

if not defined BOX_IP (
    echo [ERROR] The box answers neither on 192.168.1.101 ^(LeanLink-xxxx or CAR2-xxxx^) nor on 192.168.43.1 ^(DIRECT-xx^)!
    echo         1. Join the box Wi-Fi ^(password 88888888, some units 12345678^).
    echo         2. Unplug the LAN cable so Windows does not send the traffic elsewhere.
    pause
    exit /b 1
)

echo [1/5] Box found at http://%BOX_IP% !
set "MODEL="
set "FW_FILE="

findstr /C:".6071." "%TEMP%\car2_host.json" >nul
if not errorlevel 1 (
    set "MODEL=ly6071"
    rem newest release image wins (names sort by version)
    for %%F in ("leanlink-6071-*-LL.img") do set "FW_FILE=%%~F"
    for %%F in ("update_aa_fixed.img" "firmware\update_aa_fixed.img") do (
        if not defined FW_FILE if exist "%%~F" set "FW_FILE=%%~F"
    )
)

findstr /C:".5140." "%TEMP%\car2_host.json" >nul
if not errorlevel 1 (
    set "MODEL=ly5140"
    rem newest release image wins (names sort by version)
    for %%F in ("leanlink-5140-*-LL.img") do set "FW_FILE=%%~F"
    for %%F in ("update_5140_aa_fixed.img" "firmware_5140\update_5140_aa_fixed.img") do (
        if not defined FW_FILE if exist "%%~F" set "FW_FILE=%%~F"
    )
)

if not defined MODEL (
    echo [WARNING] This box is not a supported model ^(neither 6071 nor 5140^)! Aborted.
    echo         Box status:
    type "%TEMP%\car2_host.json"
    echo.
    pause
    exit /b 1
)

if not defined FW_FILE (
    echo [ERROR] No firmware image found for the detected model %MODEL%!
    pause
    exit /b 1
)

echo       OK - supported model %MODEL%, using image: %FW_FILE%
echo.

echo [2/5] Uploading %FW_FILE% to http://%BOX_IP% ^(about 6.7 MB^)...
curl.exe -# --max-time 90 -F "file=@%FW_FILE%;filename=blob;type=application/octet-stream" "http://%BOX_IP%/cgi-bin/index.cgi?id=upload" > "%TEMP%\car2_upload.json"
type "%TEMP%\car2_upload.json"
echo.
findstr /C:"upload successful" "%TEMP%\car2_upload.json" >nul
if errorlevel 1 (
    echo [ERROR] Upload failed!
    pause
    exit /b 1
)

echo.
echo [3/5] Image accepted! Do NOT unplug the box ^(75-90 seconds^)!
echo       The LED blinks while the flash is written...
for /L %%i in (1,1,60) do (
    timeout /t 5 /nobreak >nul
    curl.exe -s --max-time 3 "http://%BOX_IP%/cgi-bin/index.cgi?id=host" > "%TEMP%\car2_poll.json" 2>nul
    findstr /C:"\"update\": 3" "%TEMP%\car2_poll.json" >nul 2>nul
    if not errorlevel 1 goto :written
    echo       ... writing ^(%%i/60^) ...
)
echo.
echo [ERROR] The box did not report a finished write within 5 minutes.
echo         If its Wi-Fi is gone, rejoin it and open http://%BOX_IP%/ to check the version.
echo         Otherwise unplug and replug the box and run this script again.
pause
exit /b 1

:written
echo [4/5] Write complete! Setting 5 GHz ^(channel 36^) and restarting...
curl.exe -s --max-time 4 "http://%BOX_IP%/cgi-bin/index.cgi?id=set&wifi=36" >nul 2>nul
curl.exe -s --max-time 4 "http://%BOX_IP%/cgi-bin/index.cgi?id=set&conn=aoa" >nul 2>nul
timeout /t 8 /nobreak >nul
echo.
echo ====================================================================
echo [5/5] DONE! The box (%MODEL%) restarts into the new firmware ^(about 30 s^).
echo ====================================================================
pause
