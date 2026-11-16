"""Files and response records owned by one narrator run directory."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .request import render_request

SENT_WITH = ("provider", "model", "max_output_tokens", "temperature")
KEPT_FINISHES = ("complete", "other")


class RunDirectoryWriteError(Exception):
    """A write to a narrator run directory failed."""

    def __init__(self, path: Path, error: OSError) -> None:
        self.path = path
        self.error = error
        super().__init__(str(error))


class RunDirectory:
    """Read and write the files that make up a narrator run."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest.json"

    def write_plan(self, plan: Mapping[str, Any], requests: Sequence[tuple[int, Mapping[str, Any]]]) -> None:
        self.write_requests(requests)
        self._write_json(self.path / "plan.json", plan)

    def write_dossier(self, dossier: Mapping[str, Any], requests: Sequence[tuple[int, Mapping[str, Any]]]) -> None:
        self._mkdir(self.path)
        self._write_json(self.path / "dossier.json", dossier)
        self.write_requests(requests)

    def write_requests(self, requests: Sequence[tuple[int, Mapping[str, Any]]]) -> None:
        directory = self.path / "requests"
        self._mkdir(directory)
        kept: set[str] = set()
        for index, request in requests:
            name = self._numbered_name(index, len(requests))
            self._write_text(directory / name, render_request(request))
            kept.add(name)
        self._remove_stale(directory, kept)

    def prepare_responses(self, count: int) -> Path:
        directory = self.path / "responses"
        self._mkdir(directory)
        self._remove_stale(directory, {self._numbered_name(index, count) for index in range(1, count + 1)})
        return directory

    def response_path(self, index: int, count: int) -> Path:
        return self.path / "responses" / self._numbered_name(index, count)

    def request_path(self, index: int, count: int) -> Path:
        return self.path / "requests" / self._numbered_name(index, count)

    def read_plan(self) -> bytes:
        return (self.path / "plan.json").read_bytes()

    def read_optional(self, path: Path) -> bytes | None:
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def read_response(self, index: int, count: int) -> bytes | None:
        return self.read_optional(self.response_path(index, count))

    def write_response(self, index: int, count: int, record: Mapping[str, Any]) -> None:
        self._write_text(self.response_path(index, count), json.dumps(record, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def sent_with(
        provider: str, model: str | None, max_output_tokens: int, temperature: float | None
    ) -> dict[str, Any]:
        values = {
            "provider": provider,
            "model": model,
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
        return {key: values[key] for key in SENT_WITH}

    @staticmethod
    def response_record(
        *,
        index: int,
        request_sha256: str,
        sent_with: Mapping[str, Any],
        reported_model: str | None,
        finish: str,
        extra: Mapping[str, Any],
        input_tokens: int | None,
        output_tokens: int | None,
        text: str,
    ) -> dict[str, Any]:
        return {
            "index": index,
            "request_sha256": request_sha256,
            **{key: sent_with[key] for key in SENT_WITH},
            "reported_model": reported_model,
            "finish": finish,
            **extra,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "text": text,
        }

    @staticmethod
    def failure_record(sent_with: Mapping[str, Any], finish: str | None, error: str) -> dict[str, Any]:
        return {**{key: sent_with[key] for key in SENT_WITH}, "finish": finish, "error": error}

    @staticmethod
    def response_progress(record: Mapping[str, Any]) -> tuple[str, int | None, int | None]:
        finish = record["finish"]
        if not isinstance(finish, str):
            raise ValueError("response record has no finish")
        input_tokens = record.get("input_tokens")
        output_tokens = record.get("output_tokens")
        return (
            finish,
            input_tokens if isinstance(input_tokens, int) else None,
            output_tokens if isinstance(output_tokens, int) else None,
        )

    def kept_response(
        self,
        index: int,
        count: int,
        *,
        request_sha256: str,
        sent_with: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        try:
            record = json.loads(self.response_path(index, count).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        expected = {key: sent_with[key] for key in SENT_WITH}
        expected = {"request_sha256": request_sha256, **expected}
        if (
            not isinstance(record, dict)
            or any(record.get(key) != value for key, value in expected.items())
            or record.get("finish") not in KEPT_FINISHES
            or not isinstance(record.get("text"), str)
            or not record["text"].strip()
        ):
            return None
        return record

    def write_history(self, history: str, manifest: str) -> None:
        self._write_assembly("history.md", history, manifest)

    def write_articles(self, articles: str, manifest: str) -> None:
        self._write_assembly("councilors.md", articles, manifest)

    def _write_assembly(self, document_name: str, document: str, manifest: str) -> None:
        self._write_text(self.path / document_name, document)
        self._write_text(self.manifest_path, manifest)

    @staticmethod
    def _numbered_name(index: int, count: int) -> str:
        return f"{index:0{max(2, len(str(count)))}d}.json"

    @staticmethod
    def _remove_stale(directory: Path, kept: set[str]) -> None:
        for stale in sorted(directory.glob("*.json")):
            if stale.stem.isdigit() and stale.name not in kept:
                try:
                    stale.unlink()
                except OSError as error:
                    raise RunDirectoryWriteError(stale, error) from error

    @staticmethod
    def _mkdir(path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RunDirectoryWriteError(path, error) from error

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        RunDirectory._write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def _write_text(path: Path, value: str) -> None:
        try:
            path.write_text(value, encoding="utf-8", newline="\n")
        except OSError as error:
            raise RunDirectoryWriteError(path, error) from error
