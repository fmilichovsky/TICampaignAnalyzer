"""The calibration page's server: the page's files, the cached tables, and the replay the page asks for (ADR-0022).

``Calibration.handle`` answers one request without a socket; ``bind`` only wires it to a local HTTP server.
"""

from __future__ import annotations

import json
import math
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlsplit

from tinarrative.benchmarking.calibration import readout
from tinarrative.benchmarking.calibration import replay as calibration
from tinarrative.benchmarking.calibration.drafts import draft_name
from tinarrative.benchmarking.calibration.replay import ReplayError, ReplayState, ReplayStateError
from tinarrative.benchmarking.calibration.table import CalibrationTableError, read_index
from tinarrative.model.events import Significance

HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8769
PAGE_FILES: Final = ("index.html", "app.js", "style.css")
"""The page, served from the package's ``page/`` directory."""
MAX_BODY: Final = 1 << 20
_TABLE = re.compile(r"tables/([A-Za-z0-9_-][A-Za-z0-9._-]*)\.js")
_TYPES: Final = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css"}
_JSON: Final = "application/json"

Tables = dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    """The request target; a query string is ignored."""
    body: bytes = b""


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


@dataclass
class Calibration:
    """The cache directory ``out`` the page is served from, with its table loaded once per cache key."""

    out: Path
    _loaded: tuple[str, dict[str, Any], Tables, Tables] | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def handle(self, request: Request) -> Response:
        """The answer to one request: a page file, a cached table file, or ``POST /replay``; 404 for anything else."""
        path = unquote(urlsplit(request.path).path).lstrip("/") or "index.html"
        if request.method == "POST" and path == "replay":
            return self._replay(request.body)
        if request.method not in {"GET", "HEAD"}:
            return _text(HTTPStatus.METHOD_NOT_ALLOWED, "only GET and POST /replay are served")
        if path in PAGE_FILES:
            source = files("tinarrative.benchmarking.calibration").joinpath("page", path)
            return Response(HTTPStatus.OK, _TYPES[Path(path).suffix], source.read_bytes())
        if path in {"index.js", "status.js"} or _TABLE.fullmatch(path):
            try:
                content = (self.out / path).read_bytes()
            except OSError:
                return _text(HTTPStatus.NOT_FOUND, f"{path} is not in the calibration cache")
            return Response(HTTPStatus.OK, _TYPES[".js"], content)
        return _text(HTTPStatus.NOT_FOUND, f"{path} is not served here")

    def load(self) -> tuple[str, dict[str, Any], Tables, Tables]:
        """The cache key, index, rows and draft rows of ``out``, read again only once ``index.js`` names a new key."""
        key = read_index(self.out / "index.js").get("key")
        with self._lock:
            if self._loaded is None or self._loaded[0] != key:
                index, tables, drafts = calibration.load(self.out)
                self._loaded = (str(index.get("key")), index, tables, drafts)
            return self._loaded

    def _replay(self, body: bytes) -> Response:
        if len(body) > MAX_BODY:
            return _text(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "the request is too large")
        try:
            asked = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _text(HTTPStatus.BAD_REQUEST, "the request is not JSON")
        if not isinstance(asked, dict) or len(asked) != 1 or not ({"hash", "state"} & asked.keys()):
            return _text(HTTPStatus.BAD_REQUEST, 'the request is {"hash": "..."} or {"state": {...}}')
        try:
            _, index, tables, drafts = self.load()
            return _json(answer(index, tables, drafts, asked))
        except (OSError, ReplayError, CalibrationTableError) as error:
            return _json({"fatal": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)


def answer(index: Mapping[str, Any], tables: Tables, drafts: Tables, asked: Mapping[str, Any]) -> dict[str, Any]:
    """The page's answer to ``{"hash": text}`` or ``{"state": values}``: the state, its hash, the compact replay and
    the readout texts. A state that cannot be read answers with ``error`` and the code's state.

    Raises ``ReplayError`` (not a state error) for a table the replay cannot evaluate.
    """
    error = ""
    try:
        state = (
            calibration.decode_state(_string(asked["hash"]), index)
            if "hash" in asked
            else state_from_values(asked["state"], index)
        )
        result = calibration.replay(index, tables, state, drafts)
    except ReplayStateError as failure:
        error = str(failure)
        state = calibration.default_state(index)
        result = calibration.replay(index, tables, state, drafts)
    unfiltered = calibration.replay(index, tables, replace(state, types=()), drafts) if state.types else None
    state_hash = calibration.encode_state(state, index)
    document: dict[str, Any] = {
        "schema_version": calibration.SCHEMA_VERSION,
        "key": index.get("key"),
        "hash": state_hash,
        "is_code": calibration.encode_state(replace(state, focus=None), index) == "",
        "state": result["state"],
        "replay": compact(index, tables, drafts, result),
        "unfiltered": (
            None
            if unfiltered is None
            else {
                "moves": unfiltered["moves"],
                "level_counts": {name: item["level_counts"] for name, item in unfiltered["campaigns"].items()},
                "members": {name: item["members"] for name, item in unfiltered["campaigns"].items()},
            }
        ),
        "paragraph": readout.shared_paragraph(index, result),
        "snippet": readout.snippet(index, result),
        "meta": meta(index, drafts),
    }
    if error:
        document["error"] = error
    return document


def compact(index: Mapping[str, Any], tables: Tables, drafts: Tables, result: calibration.Replay) -> dict[str, Any]:
    """``result`` with each campaign's events and draft rows as columns: ``score``, ``level`` (its position in the
    level bands) and ``decided`` (the position in the campaign's rows of the row that decided it; ``None`` for a draft
    row that decided itself). Everything else is as ``replay`` gives it."""
    levels = list(index["constants"]["level_bands"])
    campaigns: dict[str, Any] = {}
    for name, item in result["campaigns"].items():
        positions = {row["id"]: position for position, row in enumerate(tables[name])}
        campaigns[name] = {
            "events": _columns(item["events"], levels, positions),
            "drafts": _columns(item["drafts"], levels, positions),
            "level_counts": item["level_counts"],
            "members": item["members"],
        }
    return {**result, "campaigns": campaigns}


def meta(index: Mapping[str, Any], drafts: Tables) -> dict[str, Any]:
    """What the page needs of the replay that no state changes: the cut-off offsets in the scale window, the score
    a base level gives, and the draft each draft row belongs to."""
    constants = index["constants"]
    return {
        "window": calibration.cutoff_offsets(),
        "level_bases": {level: Significance(level).base for level in constants["level_bands"]},
        "draft_names": {name: [draft_name(row["id"]) for row in rows] for name, rows in drafts.items()},
    }


def state_from_values(values: Any, index: Mapping[str, Any]) -> ReplayState:
    """The state the page's controls give, as ``StateResult`` writes it; keys left out keep the code's.

    Raises ``ReplayStateError`` for a value of the wrong shape, an unknown measure, campaign, draft or type, a
    reference that is not a positive number or a base that is not a level. The filter's types are checked by
    ``replay``.
    """
    if not isinstance(values, dict):
        raise ReplayStateError("the state is not an object")
    known = {"references", "campaigns", "types", "bases", "type_bases", "focus"}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ReplayStateError(f"unknown state key(s): {', '.join(unknown)}")
    default = calibration.default_state(index)
    levels = list(index["constants"]["level_bands"])
    references = dict(default.references)
    for measure, number in _mapping(values.get("references", {}), "references").items():
        if measure not in index["measures"]:
            raise ReplayStateError(f"unknown measure {measure!r} (known: {', '.join(index['measures'])})")
        if isinstance(number, bool) or not isinstance(number, int | float) or not math.isfinite(number) or number <= 0:
            raise ReplayStateError(f"the reference of {measure} must be a positive number, not {number!r}")
        references[measure] = float(number)
    campaigns = _names(values.get("campaigns", list(default.campaigns)), "campaigns")
    unknown = [name for name in campaigns if name not in index["campaigns"]]
    if unknown:
        raise ReplayStateError(f"unknown campaign(s): {', '.join(unknown)} (known: {', '.join(index['campaigns'])})")
    bases = dict(default.bases)
    for name, level in _mapping(values.get("bases", {}), "bases").items():
        if name not in bases:
            raise ReplayStateError(f"unknown draft share {name!r}")
        if level not in levels:
            raise ReplayStateError(
                f"the base of draft share {name} must be a level ({', '.join(levels)}), not {level!r}"
            )
        bases[name] = level
    type_bases: dict[str, str] = {}
    for event_type, level in _mapping(values.get("type_bases", {}), "type_bases").items():
        if event_type not in index["kinds"]:
            raise ReplayStateError(f"unknown event type {event_type!r} among the base levels")
        if level not in levels:
            raise ReplayStateError(
                f"the base level of {event_type} must be a level ({', '.join(levels)}), not {level!r}"
            )
        type_bases[event_type] = level
    focus = values.get("focus")
    if focus is not None and focus not in index["measures"]:
        raise ReplayStateError(f"unknown focus measure {focus!r}")
    state = ReplayState(
        references=references,
        campaigns=tuple(name for name in index["campaigns"] if name in campaigns),
        types=tuple(sorted(_names(values.get("types", []), "types"))),
        focus=focus,
        bases=bases,
    )
    return replace(state, type_bases=calibration.switched_types(replace(state, type_bases=type_bases), index))


def bind(calibration_page: Calibration, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """A server on ``127.0.0.1:port`` (0 for any free port) that passes each request to ``calibration_page``; the
    caller runs ``serve_forever``. Raises ``OSError`` when the port cannot be bound."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._answer(b"")

        def do_HEAD(self) -> None:
            self._answer(b"", send_body=False)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            self._answer(self.rfile.read(min(length, MAX_BODY + 1)))

        def _answer(self, body: bytes, *, send_body: bool = True) -> None:
            response = calibration_page.handle(Request(self.command, self.path, body))
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if send_body:
                self.wfile.write(response.body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the base class's name
            """Quiet: the command's own lines are the log."""

    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    return server


def url(server: ThreadingHTTPServer) -> str:
    return f"http://{HOST}:{server.server_address[1]}/"


def _columns(
    items: Sequence[calibration.EventResult], levels: list[str], positions: Mapping[str, int]
) -> dict[str, Any]:
    return {
        "score": [item["score"] for item in items],
        "level": [levels.index(item["level"]) for item in items],
        "decided": [positions.get(item["decided_by"]) for item in items],
    }


def _mapping(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReplayStateError(f"the state's {what} is not an object")
    return value


def _names(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReplayStateError(f"the state's {what} is not a list of names")
    repeated = sorted({item for item in value if value.count(item) > 1})
    if repeated:
        raise ReplayStateError(f"{what} repeated in the state: {', '.join(repeated)}")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise ReplayStateError("the state hash is not a string")
    return value


def _text(status: int, message: str) -> Response:
    return Response(status, "text/plain; charset=utf-8", message.encode("utf-8"))


def _json(document: Any, status: int = HTTPStatus.OK) -> Response:
    return Response(status, _JSON, json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("ascii"))
