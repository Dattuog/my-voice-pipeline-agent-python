import logging
import os
 
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    ChatContext,
    cli,
    metrics,
    RoomInputOptions,
)
from livekit.plugins import (
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
    google,
)
from audio_analysis_client import AudioAnalysisClient
 
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")
 
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# Model fallback options (in order of preference)
FALLBACK_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro", 
    "gemini-pro"
]

def get_llm_with_fallback():
    """Create LLM with fallback model support"""
    model_to_use = GEMINI_MODEL
    
    # If using the experimental model that hit quota, fall back
    if "2.0-flash-exp" in model_to_use:
        logger.warning(f"Model {model_to_use} may have quota issues, using fallback")
        model_to_use = FALLBACK_MODELS[0]
    
    logger.info(f"Using Gemini model: {model_to_use}")
    return google.LLM(api_key=GOOGLE_API_KEY, model=model_to_use, temperature=0.8)
 
 
class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are a professional interview agent conducting spoken interviews for a specific role. "
                "The interview topic, background, and questions are provided in your initial context. "
                "Begin the conversation as soon as the participant joins and ask them to turn on their video, and guide the interview smoothly. "
                "Ask one question at a time, listen carefully, and keep your responses short and clear. "
                "Speak naturally and avoid using complex or unpronounceable punctuation. "
                "If the context contains both technical and behavioral questions, balance them appropriately. "
                "Do not repeat the context; use it to guide your dialogue. If participant told to end the don't abruptly end the call , instead ask the reason for ending the call and if he mentions I cannot continue, then politely end the call or else continue the interview. "
            ),
            stt=deepgram.STT(),
            llm=get_llm_with_fallback(),
            tts=cartesia.TTS(),
        )
 
 
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
 
 
async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}")
    
    # Load context from local file BEFORE connecting
    context_file = "latest_context.txt"
    raw_context = ""
    if os.path.exists(context_file):
        try:
            with open(context_file, "r", encoding="utf-8") as f:
                raw_context = f.read().strip()
            logger.info(f"Loaded context from latest_context.txt: {len(raw_context)} characters")
        except Exception as e:
            logger.error(f"Error reading context file: {e}")
    else:
        logger.warning("No context file found. Starting with empty context.")
 
    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
 
    # Create initial context
    initial_ctx = ChatContext()
    if raw_context:
        # Add context as a system message instead of assistant message
        initial_ctx.add_message(role="system", content=raw_context)
        logger.info("Added context to chat context as system message")
 
    # Wait for participant
    participant = await ctx.wait_for_participant()
    logger.info(f"Starting session for participant {participant.identity}")

    # Initialize audio analysis client
    audio_client = AudioAnalysisClient()
    analysis_session_id = None
    
    # Start audio analysis for the participant
    try:
        # Check if audio analysis server is available
        health_check = await audio_client.health_check()
        if health_check.get("status") == "healthy":
            logger.info("Audio analysis server is healthy")
            
            # Start audio analysis session
            analysis_result = await audio_client.start_audio_analysis(
                room_name=ctx.room.name,
                participant_identity=participant.identity
            )
            
            if analysis_result.get("success"):
                analysis_session_id = analysis_result.get("session_id")
                logger.info(f"Audio analysis session started: {analysis_session_id}")
            else:
                logger.warning(f"Failed to start audio analysis: {analysis_result.get('error')}")
        else:
            logger.warning("Audio analysis server is not available - continuing without audio analysis")
            
    except Exception as e:
        logger.error(f"Error setting up audio analysis: {str(e)} - continuing without audio analysis")
 
    # Set up metrics
    usage_collector = metrics.UsageCollector()
 
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)
 
    # Create session
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        min_endpointing_delay=0.5,
        max_endpointing_delay=5.0,
    )
    session.on("metrics_collected", on_metrics_collected)
 
    # Start the session
    await session.start(
        room=ctx.room,
        agent=Assistant(chat_ctx=initial_ctx),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
 
    # Generate initial greeting and first question
    await session.generate_reply(
        instructions="Greet the participant warmly and start the interview with the first question based on your context. Be conversational and professional.",
        allow_interruptions=True
    )
    
    # Cleanup function for when session ends
    async def cleanup():
        if analysis_session_id:
            try:
                await audio_client.stop_audio_analysis(analysis_session_id)
                logger.info("Audio analysis session stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping audio analysis: {str(e)}")
        await audio_client.__aexit__(None, None, None)
    
    # Register cleanup handler
    try:
        # Wait for session to complete
        await session.wait_for_disconnection()
    finally:
        await cleanup()
 
 
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
 