"""Map Feishu ``im.message.receive_v1`` → ``feishu.agent_literacy.question``.

Scenario 3's detector. A trigger ``filter`` cannot do this job: filters are
exact-match JSON on payload fields, not "contains" on free text, so keyword
matching has to happen in a mapper.

Deliberately narrow, because everything it emits is answered with **zero LLM**
from a static bank:

- DM only (``chat_type == "p2p"``) — a card and its answer are addressed to
  ``open_id``, so answering a group question would arrive in the asker's DM
  instead of the group where it was asked;
- text messages from a real person (not the bot's own app messages);
- sender must be a campaign target in ``users`` — non-targets get the ordinary
  LLM reply, and the state file stays limited to the cohort;
- text must contain one of ``scenario3.keywords``.

Anything else returns ``[]`` (``filters: true`` → DEBUG, not WARNING).

State is located by ``OUTREACH_STATE_PATH`` → ``WORKSPACE_DIR/outreach/state.yaml``
→ **this file's own agent package** (``<pkg>/outreach/state.yaml``, four levels up
from ``channel_events/feishu/<slug>/``). The last one is what makes the campaign
work with no env var at all: the mapper ships inside the same package as the state
it reads, so the ordinary bring-up needs no extra configuration. Set
``OUTREACH_STATE_PATH`` only to point at a state file outside the package.

Parsed config is cached on (mtime, size), so a burst of messages re-parses the
YAML once. If no state file is found anywhere, the mapper falls back to built-in
keywords and — having no target list — emits for any DM asker.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

# Fallback list for a channel process started without OUTREACH_STATE_PATH.
_DEFAULT_KEYWORDS: tuple[str, ...] = (
    "agent",
    "智能体",
    "llm",
    "大模型",
    "海豚",
    "haitun",
    "工具调用",
    "tool calling",
    "prompt",
    "提示词",
)
_MAX_TEXT = 500
# channel_events/feishu/<slug>/map.py → the agent package root is four parents up.
_PACKAGE_STATE = Path(__file__).resolve().parents[3] / "outreach" / "state.yaml"
# (mtime_ns, size) → parsed config, so a burst of messages parses the YAML once.
_CACHE: dict[str, Any] = {"stamp": None, "config": None}


class _Config:
    __slots__ = ("enabled", "keywords", "targets")

    def __init__(self, enabled: bool, keywords: tuple[str, ...], targets: frozenset[str] | None) -> None:
        self.enabled = enabled
        self.keywords = keywords
        # None = unknown target list (no state file) → do not filter by membership.
        self.targets = targets


def _fallback_config() -> _Config:
    return _Config(True, _DEFAULT_KEYWORDS, None)


def _state_candidates() -> tuple[Path, ...]:
    """Explicit env → workspace env → this mapper's own package (no env needed)."""
    candidates: list[Path] = []
    explicit = os.environ.get("OUTREACH_STATE_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    workspace = os.environ.get("WORKSPACE_DIR", "").strip()
    if workspace:
        candidates.append(Path(workspace) / "outreach" / "state.yaml")
    candidates.append(_PACKAGE_STATE)
    return tuple(candidates)


def _load_config() -> _Config:
    """Read keywords + target open_ids from the campaign state, with an mtime cache."""
    path: Path | None = None
    stat = None
    for candidate in _state_candidates():
        try:
            stat = candidate.stat()
        except OSError:
            continue
        path = candidate
        break
    if path is None or stat is None:
        return _fallback_config()
    stamp = (str(path), stat.st_mtime_ns, stat.st_size)
    if _CACHE["stamp"] == stamp and isinstance(_CACHE["config"], _Config):
        return _CACHE["config"]
    try:
        state = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError, yaml.YAMLError:
        return _fallback_config()
    if not isinstance(state, dict):
        return _fallback_config()

    scenario = state.get("scenario3")
    scenario = scenario if isinstance(scenario, dict) else {}
    keywords = tuple(
        str(k).strip() for k in (scenario.get("keywords") or []) if isinstance(k, str | int | float) and str(k).strip()
    )
    targets = frozenset(
        str(u.get("open_id")).strip()
        for u in (state.get("users") or [])
        if isinstance(u, dict) and str(u.get("open_id") or "").strip()
    )
    config = _Config(
        enabled=scenario.get("enabled", True) is not False,
        keywords=keywords or _DEFAULT_KEYWORDS,
        targets=targets or None,
    )
    _CACHE["stamp"] = stamp
    _CACHE["config"] = config
    return config


def _delivery_id(raw: dict[str, Any]) -> str:
    header = raw.get("header")
    if isinstance(header, dict):
        event_id = header.get("event_id")
        if isinstance(event_id, str) and event_id.strip():
            return event_id.strip()
    uuid = raw.get("uuid")
    return uuid.strip() if isinstance(uuid, str) else ""


def _message_text(message: dict[str, Any]) -> str:
    """``message.content`` is a JSON string; a text message carries ``{"text": ...}``."""
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    try:
        parsed = json.loads(content)
    except ValueError:
        return content.strip()
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("text") or "").strip()


def map_event(raw: dict[str, Any]) -> list[dict[str, Any]]:
    event = raw.get("event") if isinstance(raw.get("event"), dict) else raw
    if not isinstance(event, dict):
        return []
    message = event.get("message")
    sender = event.get("sender")
    if not isinstance(message, dict) or not isinstance(sender, dict):
        return []

    # chat_id / chat_type live under event.message, not event (channel_events/README.md).
    if message.get("message_type") != "text":
        return []
    if str(message.get("chat_type") or "p2p") != "p2p":
        return []
    sender_type = sender.get("sender_type")
    if isinstance(sender_type, str) and sender_type and sender_type != "user":
        return []
    sender_id = sender.get("sender_id")
    open_id = str((sender_id or {}).get("open_id") or "").strip() if isinstance(sender_id, dict) else ""
    if not open_id:
        return []

    config = _load_config()
    if not config.enabled:
        return []
    if config.targets is not None and open_id not in config.targets:
        return []

    text = _message_text(message)[:_MAX_TEXT]
    if not text:
        return []
    lowered = text.casefold()
    keyword = next((k for k in config.keywords if k.casefold() in lowered), "")
    if not keyword:
        return []

    message_id = str(message.get("message_id") or "").strip()
    delivery = _delivery_id(raw)
    return [
        {
            "schema_version": 1,
            "source": "feishu",
            "event": "feishu.agent_literacy.question",
            "payload": {
                "open_id": open_id,
                "text": text,
                "keyword": keyword,
                "message_id": message_id,
                "chat_id": str(message.get("chat_id") or ""),
            },
            "raw_event": "im.message.receive_v1",
            "raw_payload": {"open_id": open_id, "message_id": message_id},
            "idempotency_key": f"feishu:agent_literacy:{delivery or message_id}",
            "routing": {"open_id": open_id},
        }
    ]
