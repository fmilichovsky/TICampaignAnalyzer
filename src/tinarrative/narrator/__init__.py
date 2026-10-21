"""The narrator half of the pipeline: chapter plans and requests for an LLM built from a narrator package.

Everything here reads the package's JSON form (``tinarrative events --narrative --format json``) as a plain dict
and never the model types, so this package must not import :mod:`tinarrative.parsing`,
:mod:`tinarrative.sequence` or :mod:`tinarrative.model`.
"""

from .chapters import ChapterPlan, OverBudget, base_options, plan_chapters, validate
from .request import REQUEST_KEYS, build_request, prompt_version, render_request, system_prompt

__all__ = [
    "REQUEST_KEYS",
    "ChapterPlan",
    "OverBudget",
    "base_options",
    "build_request",
    "plan_chapters",
    "prompt_version",
    "render_request",
    "system_prompt",
    "validate",
]
