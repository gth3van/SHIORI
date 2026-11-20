"""Send explicit coding requests to the Codex CLI."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_REQUEST = re.compile(r"^(?:shiori[\s,]+)?ask\s+codex\b[\s,:]*", re.IGNORECASE)
_TIMEOUT_SECONDS = 120


def get_codex_task(transcript: str) -> str | None:
    """Return the task after the activation phrase, or None for ordinary chat."""
    match = _REQUEST.match(transcript)
    if match is None:
        return None
    task = transcript[match.end():].strip()
    return task if task.strip(" .?!") else ""


async def ask_codex(task: str) -> str:
    """Run a one-shot Codex task and return the final answer for Shiori to speak."""
    executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if executable is None:
        return "I couldn't find the Codex CLI on PATH."

    prompt = (
        "You are Shiori's coding assistant for the SHIORI repository. "
        "Inspect source files as needed for this coding request. "
        "Leave files unchanged and avoid reading credentials or personal memory files. "
        "Reply in the user's language with a brief spoken summary, without Markdown.\n\n"
        f"User request: {task}"
    )
    try:
        process = await asyncio.create_subprocess_exec(
            executable, "-a", "never", "exec", "--sandbox", "read-only",
            "--ephemeral", "--ignore-user-config", "--color", "never", "-",
            cwd=_PROJECT_ROOT,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return "I couldn't start the Codex CLI."

    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(prompt.encode("utf-8")), _TIMEOUT_SECONDS
        )
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()
        if isinstance(exc, asyncio.CancelledError):
            raise
        return "Codex timed out. Try a smaller coding question."

    if process.returncode:
        print(f"[Codex] CLI exited with status {process.returncode}.", flush=True)
        return "Codex couldn't finish. Check your connection and run codex login status."
    return stdout.decode("utf-8", errors="replace").strip() or "Codex returned an empty answer."
