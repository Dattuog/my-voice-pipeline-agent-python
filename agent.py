import os
from pathlib import Path

# Add this at the VERY TOP of your file (before any other imports)
cache_dir = Path(__file__).parent / "model_cache"
os.environ["HF_HOME"] = str(cache_dir)
os.environ["TRANSFORMERS_CACHE"] = str(cache_dir)
cache_dir.mkdir(parents=True, exist_ok=True)

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    metrics,
    RoomInputOptions,
)

from livekit.plugins import (
    cartesia,
    deepgram,
    google,
    noise_cancellation,
    silero,
)
from livekit.plugins.google import LLM as GoogleLLM
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import os

# Load env vars from `.env.local`
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")

class Assistant(Agent):
    def __init__(self) -> None:
        gemini_api_key = os.environ.get("GEMINI_API_KEY")  # Changed from OPENAI_API_KEY

        super().__init__(
            instructions=(
                "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
                "You should use short and concise responses, and avoid unpronounceable punctuation. "
                "You were created as a demo to showcase the capabilities of LiveKit's agents framework."
            ),
            stt=deepgram.STT(),
            llm=google.LLM(
                model="gemini-2.0-flash-exp",
                temperature=0.8,
                api_key=gemini_api_key,
            ),
            tts=cartesia.TTS(),
            turn_detection=MultilingualModel(),
        )

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Hey, how can I help you today?", allow_interruptions=True
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

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
        agent=Assistant(),
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
