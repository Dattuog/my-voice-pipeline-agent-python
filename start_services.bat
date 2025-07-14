@echo off
echo Starting Voice Pipeline Agent with Audio Analysis...

echo.
echo Starting audio analysis server...
start "Audio Analysis Server" cmd /k "python audio_analysis_server_simple.py"

echo Waiting for server to start...
timeout /t 3

echo.
echo Testing audio analysis server...
python test_audio_server.py

echo.
echo Starting voice agent...
start "Voice Agent" cmd /k "python agent.py dev"

echo.
echo Both services are starting!
echo Audio Analysis Server: http://localhost:8000
echo Voice Agent: Running in development mode
echo.
echo Press any key to exit...
pause
