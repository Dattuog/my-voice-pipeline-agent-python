import asyncio
import aiohttp
import subprocess
import sys

async def check_services():
    print("Voice Pipeline Agent - Service Status Check")
    print("=" * 50)
    
    # Check audio analysis server
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"[OK] Audio Analysis Server: Running")
                    print(f"     Active sessions: {result.get('active_sessions', 0)}")
                    print(f"     Timestamp: {result.get('timestamp', 'N/A')}")
                else:
                    print(f"[ERROR] Audio Analysis Server: HTTP {response.status}")
    except Exception as e:
        print(f"[ERROR] Audio Analysis Server: Not responding ({str(e)})")
    
    print()
    
    # Check if agent process is running
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                              capture_output=True, text=True, check=True)
        python_processes = [line for line in result.stdout.split('\n') if 'python.exe' in line]
        
        if python_processes:
            print(f"[OK] Python Processes: {len(python_processes)} running")
            # Try to identify agent process by checking for agent.py
            agent_running = False
            for proc in python_processes:
                if 'agent.py' in proc or any('agent' in arg for arg in sys.argv):
                    agent_running = True
                    break
            
            if agent_running:
                print("[OK] Voice Agent: Likely running")
            else:
                print("[WARNING] Voice Agent: Status unclear")
        else:
            print("[ERROR] No Python processes found")
            
    except Exception as e:
        print(f"[ERROR] Could not check process status: {str(e)}")
    
    print()
    print("Service URLs:")
    print("  Audio Analysis Server: http://localhost:8000")
    print("  Voice Agent Debug: Check terminal output for debug URL")

if __name__ == "__main__":
    asyncio.run(check_services())
