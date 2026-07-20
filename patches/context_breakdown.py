"""Live session context-window breakdown for UI surfaces.

Estimates how the next provider request is composed: system prompt tiers,
tool schemas, and conversation history. Uses the same rough char/4 heuristic
as ``agent.model_metadata.estimate_request_tokens_rough`` so numbers align
with compression thresholds — not exact tokenizer counts.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hermes_constants import get_hermes_home

_SKILLS_BLOCK_RE = re.compile(r"<available_skills>.*?</available_skills>", re.DOTALL)

_SUBAGENT_TOOL_NAMES = frozenset({"delegate_task"})

_CATEGORY_COLORS = {
    "system_prompt": "var(--context-usage-system)",
    "tool_definitions": "var(--context-usage-tools)",
    "rules": "var(--context-usage-rules)",
    "skills": "var(--context-usage-skills)",
    "mcp": "var(--context-usage-mcp)",
    "subagent_definitions": "var(--context-usage-subagents)",
    "memory": "var(--context-usage-memory)",
    "conversation": "var(--context-usage-conversation)",
    "virtual_memory": "var(--context-usage-virtual)",
}


def _get_registry_path() -> Path:
    return get_hermes_home() / "sessions" / "active_swarm.json"


def update_swarm_session(
    session_id: str,
    role: str,
    workspace_mode: str,
    active: bool,
    parent_uuid: Optional[str] = None,
    goal: Optional[str] = None,
    model: Optional[str] = None,
    context_used: int = 0,
    context_max: int = 0,
) -> None:
    path = _get_registry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data[session_id] = {
            "uuid": session_id,
            "parent_uuid": parent_uuid,
            "role": role,
            "workspace_mode": workspace_mode,
            "active": active,
            "last_activity": time.time(),
            "goal": goal,
            "model": model,
            "context_used": context_used,
            "context_max": context_max,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass



def _chars_to_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def _json_tokens(value: Any) -> int:
    if not value:
        return 0
    return _chars_to_tokens(json.dumps(value, ensure_ascii=False))


def _tool_name(tool: dict) -> str:
    fn = tool.get("function") if isinstance(tool, dict) else None
    if isinstance(fn, dict):
        return str(fn.get("name") or "")
    return str(tool.get("name") or "")


def _split_tools(tools: Sequence[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    builtin: List[dict] = []
    mcp: List[dict] = []
    subagent: List[dict] = []
    for tool in tools:
        name = _tool_name(tool)
        if name.startswith("mcp_"):
            mcp.append(tool)
        elif name in _SUBAGENT_TOOL_NAMES:
            subagent.append(tool)
        else:
            builtin.append(tool)
    return builtin, mcp, subagent


def _memory_blocks(agent: Any) -> Tuple[str, str]:
    memory_block = ""
    user_block = ""
    store = getattr(agent, "_memory_store", None)
    if store is None:
        return memory_block, user_block
    try:
        if getattr(agent, "_memory_enabled", True):
            memory_block = store.format_for_system_prompt("memory") or ""
        if getattr(agent, "_user_profile_enabled", True):
            user_block = store.format_for_system_prompt("user") or ""
    except Exception:
        pass
    return memory_block, user_block


def _strip_blocks(text: str, *blocks: str) -> str:
    out = text
    for block in blocks:
        if block:
            out = out.replace(block, "")
    return out.strip()


def compute_session_context_breakdown(
    agent: Any,
    messages: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Return a Cursor-style context usage breakdown for one live agent."""
    from agent.model_metadata import estimate_messages_tokens_rough
    from agent.system_prompt import build_system_prompt_parts

    parts = build_system_prompt_parts(agent)
    stable = parts.get("stable", "") or ""
    context = parts.get("context", "") or ""
    volatile = parts.get("volatile", "") or ""

    skills_match = _SKILLS_BLOCK_RE.search(stable)
    skills_index = skills_match.group(0) if skills_match else ""

    memory_block, user_block = _memory_blocks(agent)
    memory_text = "\n\n".join(part for part in (memory_block, user_block) if part).strip()

    system_core = _strip_blocks(stable, skills_index)
    system_tail = _strip_blocks(volatile, memory_block, user_block)
    system_prompt_text = "\n\n".join(part for part in (system_core, system_tail) if part).strip()

    tools = list(getattr(agent, "tools", None) or [])
    builtin_tools, mcp_tools, subagent_tools = _split_tools(tools)

    conversation_tokens = estimate_messages_tokens_rough(messages or [])

    categories = [
        ("system_prompt", "System prompt", _chars_to_tokens(system_prompt_text)),
        ("tool_definitions", "Tool definitions", _json_tokens(builtin_tools)),
        ("rules", "Rules", _chars_to_tokens(context)),
        ("skills", "Skills", _chars_to_tokens(skills_index)),
        ("mcp", "MCP", _json_tokens(mcp_tools)),
        ("subagent_definitions", "Subagent definitions", _json_tokens(subagent_tools)),
        ("memory", "Memory", _chars_to_tokens(memory_text)),
        ("conversation", "Conversation", conversation_tokens),
    ]

    estimated_total = sum(tokens for _, _, tokens in categories)

    comp = getattr(agent, "context_compressor", None)
    db_tokens = 0
    if comp:
        db_tokens = max(0, comp.get_virtual_tokens(estimated_total) - estimated_total)

    if db_tokens > 0:
        categories.append(("virtual_memory", "Virtual RAG Memory", db_tokens))
        estimated_total += db_tokens

    context_max = int(getattr(comp, "context_length", 0) or 0) if comp else 0
    measured_used = int(getattr(comp, "last_prompt_tokens", 0) or 0) if comp else 0
    context_used = (measured_used + db_tokens) if measured_used > 0 else estimated_total
    context_percent = (
        max(0, min(100, round(context_used / context_max * 100)))
        if context_max
        else 0
    )

    # Write/update the parent agent itself in the swarm registry
    parent_id = getattr(agent, "session_id", None)
    if parent_id:
        update_swarm_session(
            session_id=parent_id,
            role="parent",
            workspace_mode="inherit",
            active=True,
            parent_uuid=None,
            goal=None,
            model=getattr(agent, "model", ""),
            context_used=context_used,
            context_max=context_max,
        )

    # Read swarm registry
    swarm_nodes = []
    cumulative_context = context_used
    decay_timeout = 60.0  # 60 seconds

    path = _get_registry_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            registry = {}

        current_time = time.time()
        for sid, entry in list(registry.items()):
            active = entry.get("active", False)
            last_activity = entry.get("last_activity", current_time)

            if not active:
                elapsed = current_time - last_activity
                decay_countdown = max(0.0, decay_timeout - elapsed)
                if decay_countdown <= 0.0:
                    # Decay complete: clean up from registry
                    try:
                        registry.pop(sid, None)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(registry, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    continue
            else:
                decay_countdown = decay_timeout

            # Filter nodes that belong to this session's swarm hierarchy
            is_descendant = False
            if sid == parent_id:
                is_descendant = True
            else:
                curr_parent = entry.get("parent_uuid")
                visited = set()
                while curr_parent and curr_parent not in visited:
                    if curr_parent == parent_id:
                        is_descendant = True
                        break
                    visited.add(curr_parent)
                    parent_entry = registry.get(curr_parent)
                    curr_parent = parent_entry.get("parent_uuid") if parent_entry else None

            if is_descendant:
                workspace_mode = entry.get("workspace_mode", "inherit")
                if workspace_mode in ("inherit", "share"):
                    sharing_state = "shared"
                else:
                    sharing_state = "isolated"

                node_context = entry.get("context_used", 0)
                if sid != parent_id:
                    cumulative_context += node_context

                swarm_nodes.append({
                    "uuid": entry.get("uuid"),
                    "parent_uuid": entry.get("parent_uuid"),
                    "role": entry.get("role", "leaf"),
                    "workspace_mode": workspace_mode,
                    "active": active,
                    "last_activity": last_activity,
                    "decay_countdown": round(decay_countdown, 1),
                    "sharing_state": sharing_state,
                    "goal": entry.get("goal"),
                    "model": entry.get("model"),
                    "context_used": node_context,
                    "context_max": entry.get("context_max", 0)
                })

    return {
        "categories": [
            {
                "color": _CATEGORY_COLORS.get(category_id, "var(--ui-text-tertiary)"),
                "id": category_id,
                "label": label,
                "tokens": tokens,
            }
            for category_id, label, tokens in categories
            if tokens > 0
        ],
        "context_max": context_max,
        "context_percent": context_percent,
        "context_used": context_used,
        "estimated_total": estimated_total,
        "model": getattr(agent, "model", "") or "",
        "swarm": {
            "cumulative_context": cumulative_context,
            "nodes": swarm_nodes
        }
    }

