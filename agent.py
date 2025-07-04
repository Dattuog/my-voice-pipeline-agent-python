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
            instructions="You are a voice assistant created by LiveKit. Your interface with users will be voice. "
                         "Use short and concise responses, and avoid unpronounceable punctuation.",
            stt=deepgram.STT(),
            llm=google.LLM(api_key=GOOGLE_API_KEY, model="gemini-2.0-flash-exp", temperature=0.8),
            tts=cartesia.TTS(),
        )
 
    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Hey, how can I help you today?", allow_interruptions=True
        )
 
 
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
 
 
async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
 
    # ✅ Load context from local file written by server.py (not metadata)
    context_file = "latest_context.txt"
    if os.path.exists(context_file):
        with open(context_file, "r") as f:
            raw_context = f.read()
        logger.info("Loaded context from latest_context.txt")
    else:
        raw_context = ""
        logger.warning("No context file found. Starting with empty context.")
 
    # ✅ Inject as single assistant message
    initial_ctx = ChatContext()
    if raw_context.strip():
        initial_ctx.add_message(role="assistant", content=raw_context)
 
    participant = await ctx.wait_for_participant()
    logger.info(f"Starting session for participant {participant.identity}")
 
    usage_collector = metrics.UsageCollector()
 
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)
 
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        min_endpointing_delay=0.5,
        max_endpointing_delay=5.0,
    )
    session.on("metrics_collected", on_metrics_collected)
 
    await session.start(
        room=ctx.room,
        agent=Assistant(chat_ctx=initial_ctx),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
 
 
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
 
 