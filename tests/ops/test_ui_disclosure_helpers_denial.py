from __future__ import annotations

import re
from pathlib import Path

import pytest
from ops.chatgpt_bridge import upload_evidence

from ops import codex_auth_relay

DENIAL_MESSAGE = "local UI disclosure helper disabled; no content was sent"
SYNTHETIC_MARKER = "synthetic-secret-payload-marker-7f021c"


def _forbidden_effect(name: str, events: list[str]):
    def fail(*_args: object, **_kwargs: object) -> None:
        events.append(name)
        raise AssertionError(f"unexpected effect: {name}")

    return fail


def _safe_observation(name: str, events: list[str], result):
    def observe(*_args: object, **_kwargs: object):
        events.append(name)
        return result

    return observe


class _SyntheticHashProbe:
    def __init__(self, marker: str, events: list[str]) -> None:
        self.marker = marker
        self.events = events

    def __format__(self, _format_spec: str) -> str:
        self.events.append("bundle hash formatted into authorization text")
        raise AssertionError("bundle hash must not be inspected")


def _assert_denied_without_echo(
    error: RuntimeError, capsys: pytest.CaptureFixture[str], marker: str
) -> None:
    assert DENIAL_MESSAGE in str(error)
    assert marker not in str(error)
    output = capsys.readouterr()
    assert marker not in output.out
    assert marker not in output.err
    assert output.out == ""
    assert output.err == ""


def test_submit_payload_denies_before_serializing_writing_or_sending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    effects: list[str] = []
    monkeypatch.setattr(
        upload_evidence.json, "dumps", _forbidden_effect("payload serialization", effects)
    )
    monkeypatch.setattr(
        upload_evidence,
        "open",
        _forbidden_effect("temporary JavaScript write", effects),
        raising=False,
    )
    monkeypatch.setattr(Path, "open", _forbidden_effect("filesystem open", effects))
    monkeypatch.setattr(Path, "write_text", _forbidden_effect("filesystem write", effects))
    monkeypatch.setattr(
        upload_evidence.subprocess,
        "run",
        _forbidden_effect("AppleScript/Chrome invocation", effects),
    )
    monkeypatch.setattr(upload_evidence.time, "sleep", _forbidden_effect("UI delay", effects))

    with pytest.raises(
        upload_evidence.LocalDisclosureDenied, match=re.escape(DENIAL_MESSAGE)
    ) as caught:
        upload_evidence.submit_payload_to_chatgpt(
            SYNTHETIC_MARKER, files_to_attach=[SYNTHETIC_MARKER]
        )

    _assert_denied_without_echo(caught.value, capsys, SYNTHETIC_MARKER)
    assert effects == []


def test_send_approval_denies_before_message_construction_or_ui_effects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    effects: list[str] = []
    monkeypatch.setattr(
        codex_auth_relay.subprocess,
        "run",
        _forbidden_effect("AppleScript/clipboard/ChatGPT invocation", effects),
    )
    monkeypatch.setattr(
        codex_auth_relay,
        "set_last_approved_hash",
        _forbidden_effect("authorization state write", effects),
    )
    monkeypatch.setattr(Path, "write_text", _forbidden_effect("filesystem write", effects))
    monkeypatch.setattr(Path, "open", _forbidden_effect("filesystem open", effects))

    with pytest.raises(
        codex_auth_relay.LocalDisclosureDenied, match=re.escape(DENIAL_MESSAGE)
    ) as caught:
        codex_auth_relay.send_approval_to_chatgpt(_SyntheticHashProbe(SYNTHETIC_MARKER, effects))

    _assert_denied_without_echo(caught.value, capsys, SYNTHETIC_MARKER)
    assert effects == []


def test_check_and_authorize_denies_before_reading_prompts_or_cached_state(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    effects: list[str] = []
    forbidden = _forbidden_effect("prompt/state read or authorization forwarding", effects)
    for name in (
        "get_latest_hash",
        "get_last_approved_hash",
        "send_approval_to_chatgpt",
    ):
        monkeypatch.setattr(codex_auth_relay, name, forbidden)
    monkeypatch.setattr(
        codex_auth_relay.glob,
        "glob",
        _safe_observation("temporary prompt scan", effects, []),
    )
    monkeypatch.setattr(
        codex_auth_relay.os.path,
        "getmtime",
        _safe_observation("temporary prompt metadata read", effects, 0.0),
    )
    monkeypatch.setattr(
        Path,
        "exists",
        _safe_observation("cached authorization state check", effects, False),
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        _safe_observation("temporary prompt/state text read", effects, ""),
    )
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(codex_auth_relay, "open", forbidden, raising=False)

    with pytest.raises(
        codex_auth_relay.LocalDisclosureDenied, match=re.escape(DENIAL_MESSAGE)
    ) as caught:
        codex_auth_relay.check_and_authorize()

    _assert_denied_without_echo(caught.value, capsys, SYNTHETIC_MARKER)
    assert effects == []
