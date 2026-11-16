from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lark.exceptions import LarkError, VisitError

from .parser import parser
from .transformer import CHRTransformer, _DeclarationTransformer

if TYPE_CHECKING:
    from lark.tree import Tree
    from lark.visitors import Transformer

    from chrpypy.program import Program
    from chrpypy.rules import Rule


def _transform(transformer: Transformer, tree: Tree) -> Any:
    """Transform while surfacing domain errors instead of Lark's wrapper."""
    try:
        return transformer.transform(tree)
    except VisitError as exc:
        raise exc.orig_exc from exc


def parse(
    source: str,
    program: Program,
    *,
    hold_compile: bool = True,
) -> Program:
    """Parse a full CHR source and add declarations/rules to ``program``."""
    tree = parser.parse(source)

    # Register declarations first so rules are independent from source order.
    _transform(_DeclarationTransformer(program), tree)

    _transform(CHRTransformer(source, program, hold_compile=hold_compile), tree)
    return program


def parse_rule(
    source: str,
    program: Program,
    *,
    hold_compile: bool = False,
) -> Rule:
    """Parse a single CHR rule and add it to ``program``.

    The trailing ``;;`` terminator is optional.
    """
    text = source.strip()

    # The ``;;`` terminator is optional. When the input is only a constraint
    # declaration, appending it would make the source invalid, so retry
    # without it before reporting a parse error.
    candidates = [text] if text.endswith(";;") else [f"{text} ;;", text]
    tree = None
    first_error: LarkError | None = None
    used_source = text
    for candidate in candidates:
        try:
            tree = parser.parse(candidate)
            used_source = candidate
            break
        except LarkError as exc:
            if first_error is None:
                first_error = exc

    if tree is None:
        if first_error is None:
            raise RuntimeError("Could not parse rule")
        raise first_error

    if next(tree.find_data("chr_constraint_declarations"), None) is not None:
        raise ValueError(
            "parse_rule expects a single rule, not constraint declarations"
        )

    rule_count = sum(1 for _ in tree.find_data("chr_rule"))
    if rule_count != 1:
        raise ValueError(
            f"parse_rule expects exactly one rule, got {rule_count}"
        )

    transformer = CHRTransformer(
        used_source, program, hold_compile=hold_compile
    )
    rules = _transform(transformer, tree)
    if len(rules) != 1:
        raise ValueError(
            f"parse_rule expects exactly one rule, got {len(rules)}"
        )
    return rules[0]
