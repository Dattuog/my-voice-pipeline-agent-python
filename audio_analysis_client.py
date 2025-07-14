import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class AudioAnalysisClient:
    """Client to interact with the simplified audio analysis server"""
    
    def __init__(self, analysis_server_url: str = "http://localhost:8000"):
        self.base_url = analysis_server_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def start_audio_analysis(self, room_name: str, participant_identity: str) -> Dict[str, Any]:
        """Start audio analysis session for a participant"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            payload = {
                "room_name": room_name,
                "participant_identity": participant_identity
            }
            
            async with self.session.post(f"{self.base_url}/start-audio-analysis", json=payload) as response:
                result = await response.json()
                
                if result.get("success"):
                    logger.info(f"Started audio analysis session for participant {participant_identity}")
                    return result
                else:
                    logger.error(f"Failed to start audio analysis: {result.get('error')}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error starting audio analysis: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def stop_audio_analysis(self, session_id: str) -> Dict[str, Any]:
        """Stop audio analysis session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            payload = {"session_id": session_id}
            
            async with self.session.post(f"{self.base_url}/stop-audio-analysis", json=payload) as response:
                result = await response.json()
                
                if result.get("success"):
                    logger.info(f"Stopped audio analysis session {session_id}")
                else:
                    logger.error(f"Failed to stop audio analysis: {result.get('error')}")
                    
                return result
                
        except Exception as e:
            logger.error(f"Error stopping audio analysis: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_active_sessions(self) -> Dict[str, Any]:
        """Get list of active audio analysis sessions"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            async with self.session.get(f"{self.base_url}/active-sessions") as response:
                result = await response.json()
                return result
                
        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return {"active_sessions": {}}
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a specific session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            async with self.session.get(f"{self.base_url}/session/{session_id}") as response:
                result = await response.json()
                return result
                
        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the audio analysis server is healthy"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                result = await response.json()
                return result
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "unhealthy", "error": str(e)}
