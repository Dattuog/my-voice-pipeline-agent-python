import asyncio
import aiohttp
import json
import sys

# Fix encoding issues on Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

async def test_audio_analysis_server():
    """Test the simplified audio analysis server endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        # Test health check
        try:
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[OK] Server is running! Health check: {result}")
                else:
                    print(f"[ERROR] Server responded with status {response.status}")
                    return False
        except aiohttp.ClientConnectorError:
            print("[ERROR] Cannot connect to audio analysis server. Make sure it's running on port 8000.")
            return False
        except Exception as e:
            print(f"[ERROR] Error testing server: {str(e)}")
            return False
        
        # Test active sessions endpoint
        try:
            async with session.get(f"{base_url}/active-sessions") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[OK] Active sessions endpoint working: {result}")
                else:
                    print(f"[ERROR] Active sessions endpoint failed with status {response.status}")
        except Exception as e:
            print(f"[ERROR] Error testing active sessions: {str(e)}")
        
        # Test start analysis endpoint
        try:
            test_payload = {
                "room_name": "test-room",
                "participant_identity": "test-participant"
            }
            async with session.post(f"{base_url}/start-audio-analysis", json=test_payload) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[OK] Start analysis endpoint working: {result}")
                    
                    # Test stop analysis if we got a session ID
                    if result.get("success") and result.get("session_id"):
                        session_id = result["session_id"]
                        stop_payload = {"session_id": session_id}
                        async with session.post(f"{base_url}/stop-audio-analysis", json=stop_payload) as stop_response:
                            if stop_response.status == 200:
                                stop_result = await stop_response.json()
                                print(f"[OK] Stop analysis endpoint working: {stop_result}")
                            else:
                                print(f"[ERROR] Stop analysis failed with status {stop_response.status}")
                else:
                    print(f"[ERROR] Start analysis endpoint failed with status {response.status}")
        except Exception as e:
            print(f"[ERROR] Error testing start/stop analysis: {str(e)}")
    
    return True

if __name__ == "__main__":
    print("Testing Audio Analysis Server...")
    success = asyncio.run(test_audio_analysis_server())
    if success:
        print("[OK] Audio analysis server test completed successfully!")
    else:
        print("[ERROR] Audio analysis server test failed!")
