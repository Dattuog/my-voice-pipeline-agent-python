#!/bin/bash

# Startup script for Voice Pipeline Agent with Audio Analysis

# Function to cleanup processes on exit
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$AUDIO_SERVER_PID" ]; then
        kill $AUDIO_SERVER_PID 2>/dev/null
    fi
    if [ ! -z "$AGENT_PID" ]; then
        kill $AGENT_PID 2>/dev/null
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "Starting Voice Pipeline Agent with Audio Analysis..."

# Create audio-analysis directory if it doesn't exist
mkdir -p audio-analysis

# Start the audio analysis server in the background
echo "Starting audio analysis server on port 8000..."
python audio_analysis_server.py &
AUDIO_SERVER_PID=$!

# Wait a moment for the server to start
sleep 3

# Check if audio server is running
if kill -0 $AUDIO_SERVER_PID 2>/dev/null; then
    echo "Audio analysis server started successfully (PID: $AUDIO_SERVER_PID)"
else
    echo "Failed to start audio analysis server"
    exit 1
fi

# Start the voice agent
echo "Starting voice pipeline agent..."
python agent.py &
AGENT_PID=$!

# Wait for both processes
wait $AGENT_PID $AUDIO_SERVER_PID
