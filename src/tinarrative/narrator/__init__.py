"""The narrator half of the pipeline: requests for an LLM built from a narrator package.

Everything here reads the package's JSON form (``tinarrative events --narrative --format json``) as a plain dict
and never the model types, so this package must not import :mod:`tinarrative.parsing`,
:mod:`tinarrative.sequence` or :mod:`tinarrative.model`.
"""

from .request import REQUEST_KEYS, build_request, prompt_version, system_prompt

__all__ = ["REQUEST_KEYS", "build_request", "prompt_version", "system_prompt"]
