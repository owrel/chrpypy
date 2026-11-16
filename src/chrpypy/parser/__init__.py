"""CHR source parser.

Parsing builds chrpypy objects directly: the Lark tree is transformed into
``Constraint``, ``Rule`` and constraint-store declarations, and rules are
registered on the target ``Program``.
"""

from __future__ import annotations

from .entry import parse, parse_rule
from .parser import parser
from .python_expr import UnsupportedExpressionError
from .transformer import CHRTransformer, UnknownConstraintError

__all__ = [
    "CHRTransformer",
    "UnknownConstraintError",
    "UnsupportedExpressionError",
    "parse",
    "parse_rule",
    "parser",
]
