"""Councilor articles: one request per dossier entry and their assembly into ``councilors.md`` with a manifest.

Reads the dossier as a plain dict; each request embeds a councilor brief and is a function of the dossier alone,
so the assembly recomputes each request hash instead of keeping a plan.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .assembly import KEPT_FINISHES, SENT_WITH, provider_lines, sent_settings, timestamp
from .brief import councilor_brief
from .request import digest, render_request
from .request import prompt_version as _prompt_version
from .request import system_prompt as _system_prompt

PROMPT_FILE = "councilor_prompt.md"
ARTICLE_KEYS = ("councilor", "faction", "length")
"""The request block in order; ``councilor`` and ``faction`` come from the entry, ``length`` from the settings."""
TITLE = "# Councilor profiles"

_HEADING = re.compile(r"^ {0,3}#{1,6}\s")


def system_prompt() -> str:
    return _system_prompt(PROMPT_FILE)


def prompt_version() -> str:
    """The SHA-256 of the councilor prompt text."""
    return _prompt_version(PROMPT_FILE)


def validate_dossier(document: object) -> dict[str, Any]:
    """The dossier as a dict; raises ``ValueError`` for anything ``tinarrative councilors`` did not write."""
    if (
        not isinstance(document, dict)
        or not isinstance(document.get("councilors"), list)
        or not isinstance(document.get("selection"), dict)
        or not all(isinstance(entry, dict) and isinstance(entry.get("name"), str) for entry in document["councilors"])
    ):
        raise ValueError("not a councilor dossier: run tinarrative councilors with --output")
    return document


def dossier_sha256(dossier: Mapping[str, Any]) -> str:
    return digest(dossier)


def article_options(dossier: Mapping[str, Any]) -> dict[str, str]:
    """The request options the settings imply: the length from ``selection.article_words``."""
    words = dossier["selection"].get("article_words")
    return {} if words is None else {"length": f"about {words} words"}


def build_article_request(
    dossier: Mapping[str, Any], index: int, options: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """The request for the councilor at 1-based ``index`` in dossier order: the brief of that entry alone.

    ``options`` defaults to ``article_options``; ``councilor`` and ``faction`` are always taken from the entry.
    """
    entries = validate_dossier(dossier)["councilors"]
    if not 1 <= index <= len(entries):
        raise ValueError(f"article {index}: the dossier has {len(entries)} councilors")
    given = article_options(dossier) if options is None else dict(options)
    unknown = sorted(set(given) - {"length"})
    if unknown:
        raise ValueError(f"unknown request keys: {', '.join(unknown)}")
    entry = entries[index - 1]
    values = {"councilor": entry["name"], "faction": entry.get("faction") or "unknown", **given}
    block = "\n".join(f"{key}: {values[key]}" for key in ARTICLE_KEYS if values.get(key))
    body = json.dumps(councilor_brief(dossier, entry), ensure_ascii=False, separators=(",", ":"))
    content = (
        f"{block}\n\nThe councilor dossier follows: its header and the entry to profile.\n\n```json\n{body}\n```\n"
    )
    return {"system": system_prompt(), "messages": [{"role": "user", "content": content}]}


def request_sha256(request: Mapping[str, Any]) -> str:
    """The hash of the request file's bytes, as ``render_request`` writes them."""
    return hashlib.sha256(render_request(request).encode("utf-8")).hexdigest()


def article_requests(dossier: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """``(index, request)`` for every councilor of the dossier, in dossier order."""
    count = len(validate_dossier(dossier)["councilors"])
    return [(index, build_article_request(dossier, index)) for index in range(1, count + 1)]


def assemble_articles(
    dossier: Mapping[str, Any],
    stored: Mapping[int, Mapping[str, Any]],
    *,
    generated: datetime,
    version: str,
    sent_with: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """``(markdown, manifest)`` from the responses ``stored`` by article index.

    An article is written only when its record was made from the recomputed request, has a kept finish and a
    text; any other record (a failure stub with ``finish`` and ``error``) is listed in the manifest only.
    ``sent_with`` are the resolved provider settings, shown when no record carries them.
    """
    entries = validate_dossier(dossier)["councilors"]
    rows: list[dict[str, Any]] = []
    written: dict[int, Mapping[str, Any]] = {}
    for index, entry in enumerate(entries, start=1):
        expected = request_sha256(build_article_request(dossier, index))
        record = stored.get(index)
        usable = (
            record is not None
            and record.get("request_sha256") == expected
            and record.get("finish") in KEPT_FINISHES
            and isinstance(record.get("text"), str)
        )
        if usable and record is not None:
            written[index] = record
        rows.append(
            {
                "index": index,
                "id": entry.get("id"),
                "name": entry["name"],
                "faction": entry.get("faction"),
                "player": entry.get("player"),
                "request_sha256": expected,
                "written": usable,
                **{key: None if record is None else record.get(key) for key in SENT_WITH},
                "reported_model": None if record is None else record.get("reported_model"),
                "finish": None if record is None else record.get("finish"),
                "error": None if record is None else record.get("error"),
                "input_tokens": None if record is None else record.get("input_tokens"),
                "output_tokens": None if record is None else record.get("output_tokens"),
            }
        )
    responses: list[Mapping[str, Any]] = list(written.values())
    if not responses and sent_with is not None:
        responses = [sent_with]
    settings = {**dossier["selection"], **sent_settings(responses)}
    manifest = {
        "program": {"name": "tinarrative", "version": version},
        "generated": timestamp(generated),
        "prompt_version": prompt_version(),
        "dossier_sha256": dossier_sha256(dossier),
        "as_of": dossier.get("as_of"),
        "source": dossier.get("source"),
        "player_faction": dossier.get("player_faction"),
        "settings": settings,
        "articles": rows,
        "tokens": {
            "input_tokens": _sum(written[index].get("input_tokens") for index in written),
            "output_tokens": _sum(written[index].get("output_tokens") for index in written),
        },
    }
    return _markdown(dossier, entries, written, responses, generated), manifest


def missing(manifest: Mapping[str, Any]) -> list[int]:
    """The indexes of the articles the manifest lists without a text."""
    return [int(row["index"]) for row in manifest["articles"] if not row["written"]]


def _markdown(
    dossier: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    written: Mapping[int, Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    generated: datetime,
) -> str:
    as_of = dossier.get("as_of")
    header = [
        TITLE,
        "",
        *provider_lines(responses),
        f"- Prompt version: {prompt_version()}",
        f"- As of: {as_of[:10] if isinstance(as_of, str) else 'unknown'}",
        f"- Player faction: {dossier.get('player_faction') or 'unknown'}",
        f"- Generated: {timestamp(generated)}",
    ]
    sections: list[str] = ["\n".join(header)]
    current: object = None
    for index, entry in enumerate(entries, start=1):
        if index not in written:
            continue
        faction = entry.get("faction") or "Unaffiliated"
        if faction != current:
            sections.append(f"## {faction}")
            current = faction
        sections.append(f"### {entry['name']}\n\n{_body(str(written[index]['text']))}")
    return "\n\n".join(sections) + "\n"


def _body(text: str) -> str:
    """The response text, without surrounding blank lines and without a title the model may have added."""
    lines = text.strip().splitlines()
    if lines and _HEADING.match(lines[0]) and not lines[0].lstrip().startswith("####"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _sum(values: Any) -> int | None:
    counts = [value for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return sum(counts) if counts else None
