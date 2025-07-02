import logging
import os
import threading
import asyncio
import sys
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment first
load_dotenv(dotenv_path=".env.local")

# Debug environment variables
print("🔍 ENVIRONMENT DEBUG:")
print(f"   RENDER_SERVICE_TYPE: '{os.environ.get('RENDER_SERVICE_TYPE')}'")
print(f"   PORT: '{os.environ.get('PORT')}'")
print(f"   Command line args: {sys.argv}")
print(f"   All relevant env vars:")
for key in os.environ:
    if any(x in key.upper() for x in ['RENDER', 'PORT', 'SERVICE']):
        print(f"     {key}: '{os.environ[key]}'")

# Only import LiveKit if we're going to use it
if len(sys.argv) > 1 and sys.argv[1] == "start":
    print("🤖 Importing LiveKit modules for worker mode...")
    from livekit.agents import (
        Agent, AgentSession, AutoSubscribe,
        JobContext, JobProcess, WorkerOptions,
        cli, metrics, RoomInputOptions
    )
    from livekit.plugins import cartesia, google, deepgram, noise_cancellation, silero
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
else:
    print("🌐 Skipping LiveKit imports for web mode...")

logger = logging.getLogger("voice-agent")
logging.basicConfig(level=logging.INFO)

# Flask app
app = Flask(__name__)

# Shared dynamic context
dynamic_context = {
    "topic": None,
    "technical_questions": [],
    "behavioral_questions": []
}

@app.route("/inject-context", methods=["POST"])
def inject_context():
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 400

    dynamic_context["topic"] = payload.get("topic")
    dynamic_context["technical_questions"] = payload.get("technical_questions", [])
    dynamic_context["behavioral_questions"] = payload.get("behavioral_questions", [])

    print("\n✅ Received Context:")
    print(dynamic_context)

    return jsonify({"status": "ok", "message": "Raw context injected"})

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy", 
        "service": "livekit-agent",
        "mode": "web" if os.environ.get("RENDER_SERVICE_TYPE") == "web" else "worker",
        "port": os.environ.get("PORT"),
        "environment": {
            "RENDER_SERVICE_TYPE": os.environ.get("RENDER_SERVICE_TYPE"),
            "PORT": os.environ.get("PORT")
        }
    }), 200

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "LiveKit Voice Agent",
        "status": "running",
        "mode": "web-only",
        "endpoints": {
            "health": "/health",
            "inject_context": "/inject-context"
        },
        "debug": {
            "port": os.environ.get("PORT"),
            "render_service_type": os.environ.get("RENDER_SERVICE_TYPE"),
            "args": sys.argv
        }
    })

def create_llm_with_context():
    """Create LLM with current dynamic context - only if LiveKit is imported"""
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    base_instruction = (
        "You are a professional voice interviewer helping the user screen candidates for roles. "
        "Keep your tone engaging and business-focused. Only ask one question at a time. "
        "If follow-up questions are given, ask them one by one based on the candidate's previous response."
    )

    question_lines = []

    topic = dynamic_context.get("topic")
    tech_qs = dynamic_context.get("technical_questions", [])
    beh_qs = dynamic_context.get("behavioral_questions", [])

    if topic:
        question_lines.append(f"The topic for this interview is: **{topic}**")
    if tech_qs:
        question_lines.append("Start with the following technical questions:")
        for i, q in enumerate(tech_qs, 1):
            question_lines.append(f"{i}. {q['question']}")
            for fq in q.get("follow_ups", []):
                question_lines.append(f"   → Follow-up: {fq}")
    if beh_qs:
        question_lines.append("\nThen move to these behavioral questions:")
        for i, q in enumerate(beh_qs, 1):
            question_lines.append(f"{i}. {q['question']}")
            for fq in q.get("follow_ups", []):
                question_lines.append(f"   → Follow-up: {fq}")

    final_instruction = base_instruction + "\n\n" + "\n".join(question_lines)
    
    return google.LLM(
        model="gemini-2.0-flash-exp",
        temperature=0.8,
        api_key=gemini_api_key,
    ), final_instruction

class Assistant(Agent):
    def __init__(self, instructions: str, llm):
        super().__init__(
            instructions=instructions,
            stt=deepgram.STT(),
            llm=llm,
            tts=cartesia.TTS(),
            turn_detection=MultilingualModel(),
        )

def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
        logger.info("VAD model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load VAD model: {e}")
        proc.userdata["vad"] = None

async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        participant = await ctx.wait_for_participant()
        logger.info(f"starting voice assistant for participant {participant.identity}")

        usage_collector = metrics.UsageCollector()

        def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
            metrics.log_metrics(agent_metrics)
            usage_collector.collect(agent_metrics)

        vad = ctx.proc.userdata.get("vad")
        
        session = AgentSession(
            vad=vad,
            min_endpointing_delay=0.5,
            max_endpointing_delay=5.0,
        )

        session.on("metrics_collected", on_metrics_collected)
        
        llm, instructions = create_llm_with_context()
        assistant = Assistant(instructions, llm)

        await session.start(
            room=ctx.room,
            agent=assistant,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        
    except Exception as e:
        logger.error(f"Error in entrypoint: {e}")
        raise
    finally:
        if hasattr(llm, 'close'):
            await llm.close()
        logger.info("Session ended and resources cleaned up")

def run_livekit_worker():
    """Run the LiveKit worker"""
    try:
        logger.info("Starting LiveKit worker...")
        
        worker_options = WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
        
        cli.run_app(worker_options)
        
    except Exception as e:
        logger.error(f"LiveKit worker failed: {e}")
        raise

def run_flask():
    """Run Flask server"""
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Flask server on port {port}")
    print(f"🌐 Flask server binding to 0.0.0.0:{port}")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    # Validate required environment variables
    required_env_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GEMINI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    print("✅ All required environment variables are set")
    
    # Decision logic with debug info
    is_web_service = os.environ.get("RENDER_SERVICE_TYPE") == "web"
    has_port_env = os.environ.get("PORT") is not None
    has_start_arg = len(sys.argv) > 1 and sys.argv[1] == "start"
    
    print(f"🔍 Decision factors:")
    print(f"   is_web_service: {is_web_service}")
    print(f"   has_port_env: {has_port_env}")
    print(f"   has_start_arg: {has_start_arg}")
    
    if has_start_arg:
        print("🤖 Starting LiveKit Worker...")
        run_livekit_worker()
    elif is_web_service or has_port_env:
        print("🌐 Running in web service mode - Flask only")
        run_flask()
    else:
        print("🚀 Local development mode - both services")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print(f"🌐 Flask server started on port {os.environ.get('PORT', 8000)}")
        run_livekit_worker()