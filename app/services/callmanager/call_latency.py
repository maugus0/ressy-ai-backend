from __future__ import annotations

from app.services.callmanager.call_state import StreamState


def log_assistant_text_latency(state: StreamState, now: float) -> None:
    if state.last_user_text_time is not None:
        print(f"[Latency] user_text->assistant_text: {now - state.last_user_text_time:.3f}s")
    if state.last_user_started_speaking_time is not None:
        print(f"[Latency] user_start->assistant_text: {now - state.last_user_started_speaking_time:.3f}s")


def log_agent_audio_start_latency(state: StreamState, now: float) -> None:
    if state.last_assistant_audio_start_time is None:
        state.last_assistant_audio_start_time = now
    if state.agent_audio_latency_logged or state.last_assistant_text_time is None:
        return
    text_to_audio = now - state.last_assistant_text_time
    user_text_to_audio = None if state.last_user_text_time is None else now - state.last_user_text_time
    user_start_to_audio = (
        None if state.last_user_started_speaking_time is None else now - state.last_user_started_speaking_time
    )
    metrics = [f"text->audio: {text_to_audio:.3f}s"]
    if user_text_to_audio is not None:
        metrics.append(f"user_text->audio: {user_text_to_audio:.3f}s")
    if user_start_to_audio is not None:
        metrics.append(f"user_start->audio: {user_start_to_audio:.3f}s")
    print(f"[Latency] Agent audio start ({', '.join(metrics)})")
    state.agent_audio_latency_logged = True
