"""The assembled history of a ``tinarrative narrate`` run, its citation audit and its manifest. See architecture 20.6.

The audit checks citations against the chapter package read back from each request, not the full package, so a
citation outside the chapter's evidence is caught. It reports and never changes or rejects prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .chapters import PLANNER_KEYS, SIGNIFICANCE
from .request import chapter_package

UNCITED_FROM = "major"
"""The lowest significance the audit expects a footnote to cite."""
KEPT_FINISHES = ("complete", "other")
"""``length`` and ``refused`` completions are never written."""
SENT_WITH = ("provider", "model", "max_output_tokens", "temperature")
"""With the request file, these response members reconstruct the request that was sent."""

_DEFINITION = re.compile(r"^ {0,3}\[\^([^\]\n]+)\]:[ \t]*(.*?)\s*$")
_REFERENCE = re.compile(r"\[\^([^\]\n]+)\](?!:)")
_NOTES_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:foot)?(?:notes|references|sources|citations)(?:\*\*)?:?\s*$", re.IGNORECASE
)
_RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_BACKTICKED = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class ChapterText:
    """``references`` are in order of first appearance."""

    body: str
    references: tuple[str, ...]
    definitions: dict[str, str]


@dataclass(frozen=True)
class StoredChapter:
    entry: Mapping[str, Any]
    request: Mapping[str, Any]
    package: Mapping[str, Any]
    response: Mapping[str, Any]

    @property
    def index(self) -> int:
        return int(self.entry["index"])

    @property
    def characters(self) -> int:
        """What the plan's estimate is made from."""
        return len(self.request["system"]) + sum(len(message["content"]) for message in self.request["messages"])


@dataclass(frozen=True)
class Assembly:
    history: str
    manifest: dict[str, Any]

    @property
    def findings(self) -> dict[str, int]:
        """Kinds without a finding are left out."""
        audit = self.manifest["audit"]
        counts = {kind: len(audit[kind] or ()) for kind in ("unmatched", "uncited", "undefined", "unreferenced")}
        return {kind: count for kind, count in counts.items() if count}


def parse_plan(data: bytes) -> dict[str, Any]:
    try:
        plan = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        plan = None
    chapters = plan.get("chapters") if isinstance(plan, dict) else None
    if (
        not isinstance(plan, dict)
        or not isinstance(chapters, list)
        or not chapters
        or not all(_is_entry(entry) for entry in chapters)
        or not isinstance(plan.get("settings"), dict)
        or not isinstance(plan.get("request"), dict)
    ):
        raise ValueError("plan.json is not a chapter plan written by tinarrative narrate")
    return plan


def stored_chapter(entry: Mapping[str, Any], request: bytes | None, response: bytes | None) -> StoredChapter:
    """Raises ``ValueError`` naming the chapter when a file is missing, invalid or made from another request than
    the plan's."""
    index = entry["index"]
    if request is None:
        raise ValueError(f"chapter {index}: no request file")
    if hashlib.sha256(request).hexdigest() != entry["request_sha256"]:
        raise ValueError(f"chapter {index}: the request file does not match plan.json")
    document = _json_object(request)
    if document is None or not isinstance(document.get("system"), str):
        raise ValueError(f"chapter {index}: the request file is not a request")
    try:
        package = chapter_package(document)
    except ValueError as error:
        raise ValueError(f"chapter {index}: {error}") from None
    if response is None:
        raise ValueError(f"chapter {index}: no response; send it with --send")
    stored = _json_object(response)
    if stored is None or not isinstance(stored.get("text"), str):
        raise ValueError(f"chapter {index}: the response file is not a response")
    if stored.get("request_sha256") != entry["request_sha256"]:
        raise ValueError(f"chapter {index}: the response was made from another request; send it again with --send")
    return StoredChapter(entry=entry, request=document, package=package, response=stored)


def split_footnotes(text: str) -> ChapterText:
    """Definitions are taken wherever they stand, with a notes heading that only introduces them."""
    lines = text.splitlines()
    kept: list[str] = []
    definitions: dict[str, str] = {}
    position = 0
    while position < len(lines):
        line = lines[position]
        match = _DEFINITION.match(line)
        if match is not None:
            parts = [match.group(2)]
            position += 1
            while position < len(lines) and lines[position].strip() and lines[position].startswith(("    ", "\t")):
                parts.append(lines[position].strip())
                position += 1
            definitions.setdefault(match.group(1).strip(), " ".join(part for part in parts if part))
            continue
        position += 1
        if _NOTES_HEADING.match(line) and _next_is_definition(lines, position):
            continue
        kept.append(line)
    body = _tidy(kept)
    references = tuple(dict.fromkeys(match.group(1).strip() for match in _REFERENCE.finditer(body)))
    return ChapterText(body=body, references=references, definitions=definitions)


def citations(definition: str) -> list[str]:
    """Backticked spans, else the parts between semicolons (or commas)."""
    spans = _BACKTICKED.findall(definition)
    parts: Iterable[str] = spans if spans else re.split(r";|,\s+", definition)
    found = (" ".join(part.split()).rstrip(".,;").strip() for part in parts)
    return [part for part in found if part]


def citable(package: Mapping[str, Any]) -> set[str]:
    """Includes ``situation <save-key>`` for each of the chapter's saves."""
    continuity = package.get("continuity") or {}
    entries = [
        *(package.get("narrative") or ()),
        *(
            event
            for interval in package.get("intervals") or ()
            for event in (*(interval.get("events") or ()), *(interval.get("inferred") or ()))
        ),
        *(continuity.get("continuing") or ()),
        *(continuity.get("earlier") or ()),
    ]
    found = {entry["id"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
    found.update(
        f"situation {save['key']}"
        for save in package.get("saves") or ()
        if isinstance(save, dict) and isinstance(save.get("key"), str)
    )
    return found


def assemble(
    chapters: Sequence[StoredChapter], plan: Mapping[str, Any], *, generated: datetime, version: str
) -> Assembly:
    """``chapters`` in plan order. Footnotes are renumbered across the history; an undefined reference is defined
    by its label."""
    footnotes = plan["request"].get("citations") != "none"
    bodies: list[str] = []
    notes: list[str] = []
    cited: set[str] = set()
    checked = 0
    unmatched: list[dict[str, Any]] = []
    undefined: list[dict[str, Any]] = []
    unreferenced: list[dict[str, Any]] = []
    expected: list[dict[str, Any]] = []
    floor = SIGNIFICANCE.index(UNCITED_FROM)
    for chapter in chapters:
        text = split_footnotes(chapter.response["text"])
        labels = [*text.references, *(label for label in text.definitions if label not in text.references)]
        numbers = {label: len(notes) + offset + 1 for offset, label in enumerate(labels)}
        allowed = citable(chapter.package)
        for label in labels:
            number = numbers[label]
            definition = text.definitions.get(label)
            if definition is None:
                undefined.append({"chapter": chapter.index, "footnote": number, "label": label})
                definition = label
                cites = [] if label.isdigit() else citations(label)
            else:
                if label not in text.references:
                    unreferenced.append({"chapter": chapter.index, "footnote": number, "label": label})
                cites = citations(definition)
            notes.append(f"[^{number}]: {definition}")
            checked += len(cites)
            cited.update(cites)
            unmatched.extend(
                {"chapter": chapter.index, "footnote": number, "id": cite} for cite in cites if cite not in allowed
            )
        bodies.append(_renumbered(text.body, numbers))
        expected.extend(
            {"chapter": chapter.index, "id": event["id"], "significance": event["significance"]}
            for event in chapter.package.get("narrative") or ()
            if event.get("significance") in SIGNIFICANCE[floor:]
        )
    uncited = [item for item in expected if item["id"] not in cited] if footnotes else None
    header = _header(chapters, plan, generated)
    history = "\n\n".join([header, *(body for body in bodies if body), *(["\n".join(notes)] if notes else [])]) + "\n"
    audit = {
        "citations": "footnotes" if footnotes else "none",
        "footnotes": len(notes),
        "cited_ids": checked,
        "unmatched": unmatched,
        "uncited": uncited,
        "undefined": undefined,
        "unreferenced": unreferenced,
    }
    return Assembly(history=history, manifest=_manifest(chapters, plan, generated, version, audit))


def _header(chapters: Sequence[StoredChapter], plan: Mapping[str, Any], generated: datetime) -> str:
    responses = [chapter.response for chapter in chapters]
    reported = _distinct(response.get("reported_model") or "not reported" for response in responses)
    requested = _distinct(str(response.get("model")) for response in responses)
    model = ", ".join(reported) + ("" if requested == reported else f" (requested {', '.join(requested)})")
    covers = _covers(chapters)
    lines = [
        "# Campaign history",
        "",
        f"- Provider: {', '.join(_distinct(str(response.get('provider')) for response in responses))}",
        f"- Model: {model}",
        f"- Prompt version: {plan.get('prompt_version')}",
        f"- Campaign: {_campaign(chapters) or 'unknown'}",
        f"- Period: {covers['from'][:10]} to {covers['to'][:10]}",
        f"- Generated: {_timestamp(generated)}",
    ]
    return "\n".join(lines)


def _manifest(
    chapters: Sequence[StoredChapter],
    plan: Mapping[str, Any],
    generated: datetime,
    version: str,
    audit: dict[str, Any],
) -> dict[str, Any]:
    responses = [chapter.response for chapter in chapters]
    settings = {key: plan["settings"].get(key) for key in PLANNER_KEYS}
    for key in SENT_WITH:
        values = list(dict.fromkeys(json.dumps(response.get(key)) for response in responses))
        settings[key] = json.loads(values[0]) if len(values) == 1 else [json.loads(value) for value in values]
    entries = [
        {
            "index": chapter.index,
            "part": chapter.entry.get("part"),
            "covers": chapter.entry["covers"],
            "periods": chapter.entry.get("periods"),
            "period": chapter.entry.get("period"),
            "period_basis": chapter.entry.get("period_basis"),
            "estimate": chapter.entry.get("estimate"),
            "reduction": chapter.entry.get("reduction"),
            "request_sha256": chapter.entry["request_sha256"],
            "request_characters": chapter.characters,
            **{key: chapter.response.get(key) for key in SENT_WITH},
            "reported_model": chapter.response.get("reported_model"),
            "finish": chapter.response.get("finish"),
            "input_tokens": chapter.response.get("input_tokens"),
            "output_tokens": chapter.response.get("output_tokens"),
        }
        for chapter in chapters
    ]
    return {
        "program": {"name": "tinarrative", "version": version},
        "generated": _timestamp(generated),
        "prompt_version": plan.get("prompt_version"),
        "package_sha256": plan.get("package_sha256"),
        "campaign": _campaign(chapters),
        "covers": _covers(chapters),
        "settings": settings,
        "request": plan["request"],
        "chapters": entries,
        "tokens": _tokens(entries),
        "audit": audit,
    }


def _tokens(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``characters_per_input_token`` is what ``chars_per_token`` is calibrated against."""
    reported = [entry for entry in entries if isinstance(entry["input_tokens"], int) and entry["input_tokens"] > 0]
    ratio = (
        round(
            sum(entry["request_characters"] for entry in reported) / sum(entry["input_tokens"] for entry in reported), 3
        )
        if reported
        else None
    )
    return {
        "estimate": sum(entry["estimate"] or 0 for entry in entries),
        "request_characters": sum(entry["request_characters"] for entry in entries),
        "input_tokens": _sum(entry["input_tokens"] for entry in entries),
        "output_tokens": _sum(entry["output_tokens"] for entry in entries),
        "characters_per_input_token": ratio,
    }


def _sum(values: Iterable[Any]) -> int | None:
    counts = [value for value in values if isinstance(value, int)]
    return sum(counts) if counts else None


def _covers(chapters: Sequence[StoredChapter]) -> dict[str, str]:
    return {"from": chapters[0].entry["covers"]["from"], "to": chapters[-1].entry["covers"]["to"]}


def _campaign(chapters: Sequence[StoredChapter]) -> str | None:
    campaign = chapters[0].package.get("campaign")
    key = campaign.get("key") if isinstance(campaign, dict) else None
    return key if isinstance(key, str) else None


def _distinct(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _renumbered(body: str, numbers: Mapping[str, int]) -> str:
    return _REFERENCE.sub(lambda match: f"[^{numbers[match.group(1).strip()]}]", body)


def _next_is_definition(lines: Sequence[str], position: int) -> bool:
    following = next((line for line in lines[position:] if line.strip()), None)
    return following is not None and _DEFINITION.match(following) is not None


def _tidy(lines: Sequence[str]) -> str:
    tidy: list[str] = []
    for line in lines:
        if not line.strip() and (not tidy or not tidy[-1].strip()):
            continue
        last = next((kept for kept in reversed(tidy) if kept.strip()), None)
        if _RULE.match(line) and last is not None and _RULE.match(last):
            continue
        tidy.append(line)
    while tidy and (not tidy[-1].strip() or _RULE.match(tidy[-1])):
        tidy.pop()
    return "\n".join(tidy)


def _is_entry(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("index"), int)
        and isinstance(entry.get("request_sha256"), str)
        and isinstance(entry.get("covers"), dict)
        and all(isinstance(entry["covers"].get(key), str) for key in ("from", "to"))
    )


def _json_object(data: bytes) -> dict[str, Any] | None:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None
