@echo off
title MyRemotePC - Internet Sharing Tunnel
echo ============================================================
echo   Creating Instant Free Internet Tunnel for Port 8080...
echo   Share the generated URL with your second PC or phone.
echo ============================================================
cmd /c "npx -y localtunnel --port 8080"
pause
