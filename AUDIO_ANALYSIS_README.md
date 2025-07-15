# Voice Pipeline Agent with Real-time Audio Analysis

This project integrates real-time audio analysis capabilities into your voice pipeline agent. The audio analysis provides insights into participant speech patterns including pitch, volume, confidence, emotion detection, and speaking rate.

## Features

### Audio Analysis Capabilities
- **Pitch Detection**: Real-time fundamental frequency analysis
- **Volume Monitoring**: RMS volume calculation and silence detection
- **Confidence Scoring**: Voice stability and clarity assessment
- **Emotion Detection**: Basic emotional state classification (calm, neutral, excited)
- **Speaking Rate**: Words-per-minute estimation
- **Real-time Processing**: Live analysis during voice sessions

### Architecture
- **Audio Analysis Server**: Standalone FastAPI server for processing audio streams
- **Voice Agent Integration**: Seamlessly integrated with your existing LiveKit agent
- **WebSocket Support**: Real-time audio streaming and analysis
- **Session Management**: Track and manage multiple analysis sessions

## Setup

### Prerequisites
```bash
pip install livekit-api numpy websockets fastapi uvicorn aiohttp
```

### Environment Configuration
Your `.env.local` should include:
```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Other API keys (Google, Deepgram, Cartesia)
GOOGLE_API_KEY=your-google-api-key
DEEPGRAM_API_KEY=your-deepgram-api-key
CARTESIA_API_KEY=your-cartesia-api-key
```

## Running the System

### Option 1: Using Batch File (Recommended for Windows)
```cmd
start_services.bat
```

### Option 2: Using PowerShell Script
```powershell
.\start_services.ps1
```

### Option 3: Manual Startup (Recommended)
1. Start the audio analysis server:
```bash
python audio_analysis_server_simple.py
```

2. In a separate terminal, start the voice agent:
```bash
python agent.py dev
```

### Option 4: Using Bash Script (Linux/Mac)
```bash
chmod +x start_services.sh
./start_services.sh
```

## Testing

Test the audio analysis server:
```bash
python test_audio_server.py
```

## API Endpoints

The audio analysis server provides the following endpoints:

### Health Check
```
GET /health
```
Returns server status and active session count.

### Start Analysis Session
```
POST /start-audio-analysis
{
    "room_name": "interview-room",
    "participant_identity": "candidate-123"
}
```

### Stop Analysis Session
```
POST /stop-audio-analysis
{
    "session_id": "session-id-here"
}
```

### Get Active Sessions
```
GET /active-sessions
```

### WebSocket Audio Stream
```
WS /ws/audio-stream/{session_id}
```
Receives raw PCM audio data and returns real-time analysis results.

## Integration Details

### Voice Agent Integration
The voice agent automatically:
1. Checks if the audio analysis server is available
2. Starts an analysis session when a participant joins
3. Continues normally if analysis is unavailable (graceful degradation)
4. Stops the analysis session when the participant leaves

### Audio Analysis Results
Each analysis frame includes:
```json
{
    "timestamp": "2025-07-13T16:59:19.578022",
    "volume": 1245.6,
    "is_silence": false,
    "pitch": 156.7,
    "speaking_rate": 1.25,
    "confidence": 0.78,
    "emotion": "neutral"
}
```

## File Structure

```
voice-pipeline-agent-python/
├── agent.py                           # Main voice agent (your existing agent)
├── audio_analysis_server_simple.py    # Simplified audio analysis server
├── audio_analysis_client.py           # Client for communication with analysis server
├── test_audio_server.py              # Test script for analysis server
├── start_services.ps1                # PowerShell startup script
├── start_services.sh                 # Bash startup script
├── .env.local                        # Environment variables
├── requirements.txt                   # Python dependencies
└── audio-analysis/                   # Directory for analysis data
```

## Customization

### Extending Audio Analysis
You can enhance the audio analysis by:

1. **Adding ML Models**: Integrate librosa, speech_recognition, or custom models
2. **Emotion Recognition**: Use pre-trained emotion detection models
3. **Advanced Speech Features**: Add MFCC, spectrograms, or voice quality metrics
4. **Real-time Feedback**: Send analysis results back to participants

### Example Custom Analysis
```python
def advanced_emotion_detection(self, audio_array):
    # Your ML model integration here
    # Example: using transformers for emotion recognition
    features = extract_features(audio_array)
    emotion = emotion_model.predict(features)
    return emotion
```

## Troubleshooting

### Common Issues

1. **Server Connection Failed**
   - Ensure the audio analysis server is running on port 8000
   - Check firewall settings
   - Verify no other services are using port 8000

2. **Audio Analysis Not Starting**
   - Check LiveKit credentials in `.env.local`
   - Verify participant has audio track
   - Check server logs for errors

3. **Frontend Integration Issues**
   - **"Failed to start recording: undefined"** error:
     - Check if server is running: `netstat -ano | findstr :8000`
     - Verify API endpoint: `http://localhost:8000/start-audio-analysis`
     - Check request payload includes `room_name` field
     - See `FRONTEND_INTEGRATION_GUIDE.md` for detailed examples
   - **CORS Issues**: Server is configured for `localhost:3000`
   - **Network Errors**: Check browser console and network tab

4. **Performance Issues**
   - Adjust analysis frequency in the audio analyzer
   - Consider using background processing for heavy ML models
   - Monitor CPU usage during analysis

### Logs
- Audio analysis server logs appear in the terminal
- Voice agent logs include analysis status
- Use `GET /active-sessions` to monitor session status

## Production Considerations

1. **Scalability**: Consider using Redis for session management in multi-instance deployments
2. **Security**: Add authentication to audio analysis endpoints
3. **Performance**: Implement audio buffering and batch processing for heavy analysis
4. **Storage**: Add database integration for storing analysis results
5. **Monitoring**: Implement proper logging and metrics collection

## Next Steps

1. **Enhanced Analysis**: Integrate advanced ML models for better emotion and speech quality detection
2. **Dashboard**: Create a web dashboard to visualize analysis results
3. **Alerts**: Implement real-time alerts based on analysis thresholds
4. **Export**: Add functionality to export analysis data for further processing
5. **Integration**: Connect with your existing interview evaluation systems

The audio analysis feature is designed to be non-invasive and will gracefully handle cases where the analysis server is unavailable, ensuring your voice agent continues to function normally.
