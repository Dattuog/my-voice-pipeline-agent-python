import logging
import os
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv
 
from livekit.agents import (
    Agent, AgentSession, AutoSubscribe,
    JobContext, JobProcess, WorkerOptions,
    cli, metrics, RoomInputOptions
)
from livekit.plugins import cartesia, google, deepgram, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
 
# Load environment
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")
 
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
 
 
class Assistant(Agent):
    def __init__(self):
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
 
        super().__init__(
            instructions=final_instruction,
            stt=deepgram.STT(),
            llm=google.LLM(
                model="gemini-2.0-flash-exp",
                temperature=0.8,
                api_key=gemini_api_key,
            ),
            tts=cartesia.TTS(),
            turn_detection=MultilingualModel(),
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
 
def run_flask():
    app.run(host="0.0.0.0", port=8000)
 
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
 
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
 
 