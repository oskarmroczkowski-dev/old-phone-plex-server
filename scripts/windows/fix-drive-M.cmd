@echo off
chcp 65001 >nul
title Fix drive M: - Plex phone server

rem --- configuration ---
set "PHONE_IP=192.168.1.50"
set "PHONE_USER=u0_a123"
set "SSH_PORT=8022"
set "USB_ID=ABCD-1234"
set "MEDIA_DIR=Media"
set "MOVIES_DIR=Movies"
rem ---------------------

set "SHARE=\\sshfs.kr\%PHONE_USER%@%PHONE_IP%!%SSH_PORT%\storage\%USB_ID%\%MEDIA_DIR%"

echo Checking whether the phone responds...
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { if ($c.ConnectAsync('%PHONE_IP%',%SSH_PORT%).Wait(5000)) { exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
  echo.
  echo [ERROR] The phone does not respond.
  echo  - check that the phone is on and connected to Wi-Fi,
  echo  - open the Termux app on the phone, it will start the server.
  echo Then run this shortcut again.
  goto end
)

if exist "M:\%MOVIES_DIR%\" (
  echo.
  echo [OK] Drive M: works. Nothing to change.
  goto end
)

echo Connecting drive M:...
net use M: /delete /y >nul 2>&1
net use M: "%SHARE%" /persistent:yes
if exist "M:\%MOVIES_DIR%\" (
  echo.
  echo [OK] Drive M: is back.
) else (
  echo.
  echo [ERROR] Could not connect M:. Take a screenshot of this window.
)

:end
echo.
pause
