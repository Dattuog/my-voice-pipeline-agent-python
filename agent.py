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
    openai,
    deepgram,
    noise_cancellation,
    silero,
    google,
)
 
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")
 
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
 
 
class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext) -> None:
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are a professional interview agent conducting spoken interviews for a specific role. "
                "The interview topic, background, and questions are provided in your initial context. "
                "Begin the conversation as soon as the participant joins, and guide the interview smoothly. "
                "Ask one question at a time, listen carefully, and keep your responses short and clear. "
                "Speak naturally and avoid using complex or unpronounceable punctuation. "
                "If the context contains both technical and behavioral questions, balance them appropriately. "
                "Do not repeat the context; use it to guide your dialogue."
            ),
            stt=deepgram.STT(),
            llm=google.LLM(api_key=GOOGLE_API_KEY, model="gemini-2.0-flash-exp", temperature=0.8),
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
 
 
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
 