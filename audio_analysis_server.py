import asyncio
import websockets
import json
import numpy as np
from livekit import api
from livekit.api import LiveKitAPI
from livekit.protocol import egress as egress_proto
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import wave
import io
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware for NextJS frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your NextJS app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LiveKit API client
livekit_api = LiveKitAPI(
    url=os.environ.get("LIVEKIT_URL", "wss://agents-gijygldl.livekit.cloud").replace("wss://", "https://"),
    api_key=os.environ.get("LIVEKIT_API_KEY"),
    api_secret=os.environ.get("LIVEKIT_API_SECRET")
)

# Store active egress sessions
active_egress = {}

class AudioAnalyzer:
    def __init__(self):
        self.audio_buffer = []
        self.sample_rate = 48000
        self.channels = 1
        
    def analyze_audio_chunk(self, audio_data):
        """Analyze audio chunk for various metrics"""
        # Convert bytes to numpy array (16-bit signed PCM)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate basic metrics
        volume = np.sqrt(np.mean(audio_array**2))
        silence_threshold = 500  # Adjust based on your needs
        is_silence = volume < silence_threshold
        
        # Detect pitch (basic implementation)
        pitch = self.detect_pitch(audio_array)
        
        # Detect speaking rate
        speaking_rate = self.calculate_speaking_rate(audio_array)
        
        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "volume": float(volume),
            "is_silence": is_silence,
            "pitch": pitch,
            "speaking_rate": speaking_rate,
            "confidence": self.calculate_confidence(audio_array),
            "emotion": self.detect_emotion(audio_array)
        }
        
        return analysis_result
    
    def detect_pitch(self, audio_array):
        """Basic pitch detection using autocorrelation"""
        if len(audio_array) < 1024:
            return 0
        
        # Simple autocorrelation-based pitch detection
        autocorr = np.correlate(audio_array, audio_array, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Find the first peak after the zero lag
        peak_idx = np.argmax(autocorr[100:]) + 100
        if peak_idx > 0:
            pitch = self.sample_rate / peak_idx
            return float(pitch) if 50 <= pitch <= 800 else 0
        return 0
    
    def calculate_speaking_rate(self, audio_array):
        """Calculate speaking rate (words per minute estimate)"""
        # This is a simplified implementation
        # In practice, you'd use more sophisticated speech recognition
        volume = np.sqrt(np.mean(audio_array**2))
        return float(volume / 1000)  # Simplified metric
    
    def calculate_confidence(self, audio_array):
        """Calculate confidence score based on audio characteristics"""
        volume = np.sqrt(np.mean(audio_array**2))
        stability = 1.0 - (np.std(audio_array) / np.mean(np.abs(audio_array) + 1e-10))
        return float(min(max(volume / 2000 * stability, 0), 1))
    
    def detect_emotion(self, audio_array):
        """Basic emotion detection (placeholder)"""
        # This would typically use ML models like librosa + trained classifiers
        volume = np.sqrt(np.mean(audio_array**2))
        if volume > 2000:
            return "excited"
        elif volume < 500:
            return "calm"
        else:
            return "neutral"

# Initialize audio analyzer
audio_analyzer = AudioAnalyzer()

@app.post("/start-audio-recording")
async def start_audio_recording(request: dict):
    """Start audio recording for a specific track"""
    room_name = request.get("room_name")
    track_id = request.get("track_id")
    participant_identity = request.get("participant_identity", "unknown")
    
    try:
        # WebSocket URL for real-time analysis
        websocket_url = f"ws://localhost:8000/ws/audio-stream?track_id={track_id}&participant={participant_identity}"
        
        # Create track egress request for WebSocket streaming
        track_request = TrackEgressRequest(
            room_name=room_name,
            track_id=track_id,
            websocket_url=websocket_url
        )
        
        # Start the egress
        egress_info = await egress_client.start_track_egress(track_request)
        
        # Store egress info
        active_egress[egress_info.egress_id] = {
            "track_id": track_id,
            "participant": participant_identity,
            "room_name": room_name,
            "status": "active"
        }
        
        logger.info(f"Started audio recording for track {track_id}, egress ID: {egress_info.egress_id}")
        
        return {
            "success": True,
            "egress_id": egress_info.egress_id,
            "message": "Audio recording started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting audio recording: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/stop-audio-recording")
async def stop_audio_recording(request: dict):
    """Stop audio recording"""
    egress_id = request.get("egress_id")
    
    try:
        # Stop the egress
        await egress_client.stop_egress(egress_id)
        
        # Remove from active sessions
        if egress_id in active_egress:
            del active_egress[egress_id]
        
        logger.info(f"Stopped audio recording for egress {egress_id}")
        
        return {
            "success": True,
            "message": "Audio recording stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Error stopping audio recording: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.websocket("/ws/audio-stream")
async def websocket_audio_stream(websocket: WebSocket):
    """WebSocket endpoint to receive audio stream from LiveKit"""
    await websocket.accept()
    
    # Get query parameters
    track_id = websocket.query_params.get("track_id")
    participant = websocket.query_params.get("participant")
    
    logger.info(f"WebSocket connection established for track {track_id}, participant {participant}")
    
    try:
        while True:
            # Receive data from LiveKit egress
            data = await websocket.receive()
            
            if data["type"] == "websocket.receive":
                if "bytes" in data:
                    # Binary frame - raw PCM audio data
                    audio_data = data["bytes"]
                    
                    # Analyze audio in real-time
                    analysis_result = audio_analyzer.analyze_audio_chunk(audio_data)
                    
                    # Log analysis results (or send to your analysis pipeline)
                    logger.info(f"Audio analysis: {analysis_result}")
                    
                    # You can send analysis results back to frontend if needed
                    # await websocket.send_json(analysis_result)
                    
                elif "text" in data:
                    # Text frame - event notification
                    event_data = json.loads(data["text"])
                    logger.info(f"Track event: {event_data}")
                    
                    if event_data.get("muted"):
                        logger.info("Track muted - pausing analysis")
                    else:
                        logger.info("Track unmuted - resuming analysis")
                        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for track {track_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")

@app.get("/active-recordings")
async def get_active_recordings():
    """Get list of active recordings"""
    return {"active_egress": active_egress}

# Optional: File storage for batch analysis
@app.post("/start-file-recording")
async def start_file_recording(request: dict):
    """Start audio recording to file storage"""
    room_name = request.get("room_name")
    track_id = request.get("track_id")
    participant_identity = request.get("participant_identity", "unknown")
    
    try:
        # File output configuration (local storage for now)
        file_output = DirectFileOutput(
            filepath=f"audio-analysis/{room_name}/{participant_identity}-{track_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
        )
        
        # Create track egress request for file storage
        track_request = TrackEgressRequest(
            room_name=room_name,
            track_id=track_id,
            file=file_output
        )
        
        # Start the egress
        egress_info = await egress_client.start_track_egress(track_request)
        
        return {
            "success": True,
            "egress_id": egress_info.egress_id,
            "message": "File recording started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting file recording: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
