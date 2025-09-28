from __future__ import annotations as _annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai.tools import Tool


MINIZINC_GETTING_STARTED_URL = "https://python.minizinc.dev/en/latest/getting_started.html"


@dataclass
class MiniZincDocs:
    """Minimal docs tool exposing MiniZinc Python getting started URL.

    This replaces the previous MCP-provided tools by offering a simple,
    deterministic tool that returns the canonical docs link for MiniZinc Python.
    """

    def get_getting_started_url(self) -> str:  # noqa: D401
        """Return the MiniZinc Python Getting Started URL."""
        return MINIZINC_GETTING_STARTED_URL


def build_tools() -> list[Tool[Any]]:
    docs = MiniZincDocs()

    return [
        Tool(
            lambda: docs.get_getting_started_url(),
            name="minizinc_getting_started",
            description=(
                "Return the MiniZinc Python Getting Started docs URL. Use this when"
                " the user needs installation or usage guidance for MiniZinc"
            ),
        )
    ]


