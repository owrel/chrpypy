from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from lark.exceptions import LarkError, VisitError
from lark.tree import Tree

from .parser import parser
from .transformer import RuleTransformer, _ConstraintDeclarationTransformer

if TYPE_CHECKING:
    from pathlib import Path

    from lark.visitors import Transformer

    from chrpypy.program import Program
    from chrpypy.rules import Rule


def _transform(transformer: Transformer, tree: Tree) -> Any:
    """Transform while surfacing domain errors instead of Lark's wrapper."""
    try:
        return transformer.transform(tree)
    except VisitError as exc:
        raise exc.orig_exc from exc


def _split_statements(tree: Tree) -> tuple[Tree, Tree]:
    """Separate a parsed source into declaration and rule statements.

    This makes the ordering explicit: declarations are always applied before
    rules, regardless of the order they appear in the source.
    """
    declarations: list[Tree] = []
    rules: list[Tree] = []
    for statement in tree.children:
        if statement.data == "chr_constraint_declarations":
            declarations.append(statement)
        elif statement.data == "chr_rule":
            rules.append(statement)
        else:
            raise ValueError(f"Unexpected statement: {statement.data}")

    return Tree("start", declarations), Tree("start", rules)


def parse_program(
    source: str,
    name: str | None = None,
    *,
    folder: Path | str | None = None,
    use_cache: bool = True,
    compile_on: Literal["first_post", "rule", "compile"] = "compile",
    max_history: int = 50,
    auto_reset_rules: bool = True,
    hold_compile: bool = True,
) -> Program:
    from chrpypy.program import Program  # noqa: PLC0415

    program = Program(
        name=name,
        folder=folder,
        use_cache=use_cache,
        compile_on=compile_on,
        max_history=max_history,
        auto_reset_rules=auto_reset_rules,
    )

    declarations, rules = _split_statements(parser.parse(source))

    # Declarations first, then rules, independently of source order.
    _transform(_ConstraintDeclarationTransformer(program), declarations)
    _transform(
        RuleTransformer(source, program, hold_compile=hold_compile), rules
    )
    return program


def parse_rule(
    source: str,
    program: Program,
    *,
    hold_compile: bool = False,
) -> Rule:

    text = source.strip()

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

    transformer = RuleTransformer(
        used_source, program, hold_compile=hold_compile
    )
    rules = _transform(transformer, tree)
    if len(rules) != 1:
        raise ValueError(
            f"parse_rule expects exactly one rule, got {len(rules)}"
        )
    return rules[0]
