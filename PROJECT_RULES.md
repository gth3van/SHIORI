# AI Assistant Companion - Architecture & Coding Guidelines

## Tech Stack
- Language: Python 3.10+
- Architecture: Asyncio event loop with modular services
- Subsystems:
  1. STT (Speech-to-Text): Faster-Whisper / SpeechRecognition
  2. Brain: OpenAI-compatible API client (Ollama / Groq / OpenAI)
  3. TTS (Text-to-Speech): Edge-TTS / Voicevox
  4. Visual/Avatar: WebSocket client for Live2D / VTube Studio

## Code Conventions
- Keep all modules decoupled into separate files:
  - `brain/llm_engine.py` (Dialogue handling)
  - `voice/stt_listener.py` (Microphone stream & transcription)
  - `voice/tts_speaker.py` (Speech synthesis & audio queue)
  - `main.py` (Central orchestrator)
- Always use explicit type hints and async/await for non-blocking I/O.
- Provide full, runnable code blocks without placeholder comments (e.g., `# TODO`).