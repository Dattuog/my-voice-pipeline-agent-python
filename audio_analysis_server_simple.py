import asyncio
import json
import numpy as np
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],  # More permissive for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Store active analysis sessions
active_sessions = {}

class AudioAnalyzer:
    def __init__(self):
        self.audio_buffer = []
        self.sample_rate = 48000
        self.channels = 1
        
    def analyze_audio_chunk(self, audio_data):
        """Analyze audio chunk for various metrics"""
        try:
            # Convert bytes to numpy array (16-bit signed PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            if len(audio_array) == 0:
                return None
            
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
        except Exception as e:
            logger.error(f"Error analyzing audio chunk: {str(e)}")
            return None
    
    def detect_pitch(self, audio_array):
        """Basic pitch detection using autocorrelation"""
        try:
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
        except Exception:
            return 0
    
    def calculate_speaking_rate(self, audio_array):
        """Calculate speaking rate (words per minute estimate)"""
        try:
            # This is a simplified implementation
            # In practice, you'd use more sophisticated speech recognition
            volume = np.sqrt(np.mean(audio_array**2))
            return float(volume / 1000)  # Simplified metric
        except Exception:
            return 0.0
    
    def calculate_confidence(self, audio_array):
        """Calculate confidence score based on audio characteristics"""
        try:
            volume = np.sqrt(np.mean(audio_array**2))
            stability = 1.0 - (np.std(audio_array) / np.mean(np.abs(audio_array) + 1e-10))
            return float(min(max(volume / 2000 * stability, 0), 1))
        except Exception:
            return 0.0
    
    def detect_emotion(self, audio_array):
        """Basic emotion detection (placeholder)"""
        try:
            # This would typically use ML models like librosa + trained classifiers
            volume = np.sqrt(np.mean(audio_array**2))
            if volume > 2000:
                return "excited"
            elif volume < 500:
                return "calm"
            else:
                return "neutral"
        except Exception:
            return "unknown"

# Initialize audio analyzer
audio_analyzer = AudioAnalyzer()

@app.post("/start-audio-analysis")
async def start_audio_analysis(request: dict):
    """Start audio analysis for a participant"""
    try:
        logger.info(f"Received start analysis request: {request}")
        
        room_name = request.get("room_name")
        participant_identity = request.get("participant_identity", "unknown")
        
        if not room_name:
            logger.error("Missing room_name in request")
            return {
                "success": False,
                "error": "room_name is required"
            }
        
        session_id = f"{room_name}_{participant_identity}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store session info
        active_sessions[session_id] = {
            "room_name": room_name,
            "participant": participant_identity,
            "status": "active",
            "start_time": datetime.now().isoformat(),
            "analysis_count": 0
        }
        
        logger.info(f"Started audio analysis session: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Audio analysis session started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting audio analysis: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/stop-audio-analysis")
async def stop_audio_analysis(request: dict):
    """Stop audio analysis session"""
    session_id = request.get("session_id")
    
    try:
        # Remove from active sessions
        if session_id in active_sessions:
            session_info = active_sessions[session_id]
            del active_sessions[session_id]
            logger.info(f"Stopped audio analysis session: {session_id}")
            
            return {
                "success": True,
                "message": "Audio analysis session stopped successfully",
                "session_info": session_info
            }
        else:
            return {
                "success": False,
                "error": "Session not found"
            }
        
    except Exception as e:
        logger.error(f"Error stopping audio analysis: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.websocket("/ws/audio-stream/{session_id}")
async def websocket_audio_stream(websocket: WebSocket, session_id: str):
    """WebSocket endpoint to receive audio stream for analysis"""
    await websocket.accept()
    
    logger.info(f"WebSocket connection established for session {session_id}")
    
    if session_id not in active_sessions:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    try:
        while True:
            # Receive data from client
            data = await websocket.receive()
            
            if data["type"] == "websocket.receive":
                if "bytes" in data:
                    # Binary frame - raw PCM audio data
                    audio_data = data["bytes"]
                    
                    # Analyze audio in real-time
                    analysis_result = audio_analyzer.analyze_audio_chunk(audio_data)
                    
                    if analysis_result:
                        # Update session stats
                        active_sessions[session_id]["analysis_count"] += 1
                        active_sessions[session_id]["last_analysis"] = analysis_result["timestamp"]
                        
                        # Log analysis results
                        logger.info(f"Audio analysis [{session_id}]: Volume={analysis_result['volume']:.1f}, Pitch={analysis_result['pitch']:.1f}Hz, Emotion={analysis_result['emotion']}")
                        
                        # Send analysis results back to client
                        await websocket.send_json({
                            "type": "analysis",
                            "session_id": session_id,
                            "data": analysis_result
                        })
                    
                elif "text" in data:
                    # Text frame - control message
                    try:
                        message = json.loads(data["text"])
                        logger.info(f"Control message [{session_id}]: {message}")
                        
                        if message.get("type") == "ping":
                            await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON message received: {data['text']}")
                        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error [{session_id}]: {str(e)}")
    finally:
        # Mark session as inactive
        if session_id in active_sessions:
            active_sessions[session_id]["status"] = "disconnected"
            active_sessions[session_id]["end_time"] = datetime.now().isoformat()

@app.get("/active-sessions")
async def get_active_sessions():
    """Get list of active analysis sessions"""
    return {"active_sessions": active_sessions}

@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get information about a specific session"""
    if session_id in active_sessions:
        return {"session": active_sessions[session_id]}
    else:
        return {"error": "Session not found"}

@app.get("/")
async def root():
    """Root endpoint for testing connectivity"""
    return {
        "service": "Voice Pipeline Audio Analysis Server",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "start_analysis": "/start-audio-analysis",
            "stop_analysis": "/stop-audio-analysis",
            "active_sessions": "/active-sessions",
            "websocket": "/ws/audio-stream/{session_id}"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    }

if __name__ == "__main__":
    import uvicorn
    # Create audio-analysis directory if it doesn't exist
    os.makedirs("audio-analysis", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
