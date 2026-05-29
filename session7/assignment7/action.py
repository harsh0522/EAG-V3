"""Action: pure MCP dispatch, artifact-handle guard, artifact threshold."""
from __future__ import annotations
import re
from mcp import ClientSession
from memory import ArtifactStore
import logger as log
from schemas import ToolCall

ARTIFACT_THRESHOLD_BYTES = 4096
_PATH_KEYS = re.compile(r"^(path|url|file|location)$", re.IGNORECASE)


class Action:
    def __init__(self, artifacts: ArtifactStore):
        self.artifacts = artifacts

    async def execute(
        self,
        session: ClientSession,
        tool_call: ToolCall,
    ) -> tuple[str, str | None]:
        # Guard: artifact handle passed as path/url/file/location
        for key, val in tool_call.arguments.items():
            if _PATH_KEYS.match(key) and isinstance(val, str) and val.startswith("art:"):
                log.action_guarded(log._CURRENT_ITER, tool_call)
                return (
                    "error: artifact handles are not paths/urls — read attached bytes in the prompt instead",
                    None,
                )

        result = await session.call_tool(tool_call.name, arguments=tool_call.arguments)

        parts = []
        for block in (result.content or []):
            if hasattr(block, "text"):
                parts.append(block.text)
            elif isinstance(block, dict):
                parts.append(block.get("text", str(block)))
            else:
                parts.append(str(block))
        text = "\n".join(parts)

        should_artifact = (
            tool_call.name == "web_search"
            or len(text.encode("utf-8")) > ARTIFACT_THRESHOLD_BYTES
        )
        if should_artifact:
            content_type = "text/markdown" if tool_call.name == "fetch_url" else "text/plain"
            args_repr = ", ".join(f"{v!r}"[:30] for v in list(tool_call.arguments.values())[:2])
            descriptor = f"{tool_call.name}({args_repr})"
            art_id = self.artifacts.put(
                text.encode("utf-8"),
                content_type=content_type,
                source=tool_call.name,
                descriptor=descriptor,
            )
            n = len(text.encode("utf-8"))
            return (f"[artifact {art_id}, {n} bytes] preview: {text[:300]}", art_id)

        return (text, None)
