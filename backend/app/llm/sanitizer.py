"""Prompt-injection neutralisation.

Filtering is defence in depth. The REAL control is structural: the classifier's
output type is a closed enum, so even a successful injection cannot emit an action.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

_MAX_CHARS = 512
_ROLE_MARKERS = re.compile(
    r"(?i)(?:^|\s)(system|assistant|user|developer)\s*:|"
    r"<\|[^>]*\|>|\[/?INST\]|<<SYS>>|###\s*(?:instruction|system)",
)
_FENCES = re.compile(r"```|~~~|</?[a-zA-Z][^>]*>")
_URLS = re.compile(r"https?://\S+|www\.\S+")
_CTRL = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\x00-\x08\x0b\x0c\x0e-\x1f]")
_IMPERATIVES = re.compile(
    r"(?i)\b(ignore|disregard|forget|override|bypass)\s+(all\s+|the\s+|previous\s+|prior\s+|above\s+)*"
    r"(instruction|prompt|rule|context|system)",
)


@dataclass
class SanitizerReport:
    masked_count: int = 0
    stripped_markers: int = 0
    stripped_urls: int = 0
    truncated: bool = False
    injection_suspected: bool = False


def sanitize(text: str) -> tuple[str, SanitizerReport]:
    rep = SanitizerReport()
    if not text:
        return "", rep
    out = _CTRL.sub("", text)
    out, n1 = _ROLE_MARKERS.subn(" ", out)
    out, n2 = _IMPERATIVES.subn(" ", out)
    out, n3 = _FENCES.subn(" ", out)
    out, n4 = _URLS.subn(" ", out)
    rep.stripped_markers = n1 + n2 + n3
    rep.stripped_urls = n4
    rep.injection_suspected = (n1 + n2) > 0
    if len(out) > _MAX_CHARS:
        out, rep.truncated = out[:_MAX_CHARS], True
    return re.sub(r"\s+", " ", out).strip(), rep
