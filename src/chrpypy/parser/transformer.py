from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from lark.visitors import Transformer, v_args

from chrpypy.constraints import Constraint
from chrpypy.expressions import FAILURE, SUCCESS, And, FunctionCall, Unification
from chrpypy.rules import (
    PropagationRule,
    Rule,
    SimpagationRule,
    SimplificationRule,
)
from chrpypy.typesystem import TypeSystem

from .python_expr import translate_expression, translate_guard

if TYPE_CHECKING:
    from lark.tree import Meta

    from chrpypy.expressions import Expression, Failure, Guard, Success
    from chrpypy.program import Program


class UnknownConstraintError(NameError):
    def __init__(self, name: str, meta: Meta | None = None) -> None:
        location = ""
        if meta is not None and meta.line is not None:
            location = f" (line {meta.line}, column {meta.column})"
        super().__init__(f"Unknown constraint '{name}'{location}")
        self.name = name


def _format_pragmas(pragmas: frozenset[str]) -> str:
    if len(pragmas) == 1:
        return next(iter(pragmas))
    return "{" + ", ".join(sorted(pragmas)) + "}"


def _flatten_pragmas(children: list[Any]) -> frozenset[str]:
    if not children:
        return frozenset()

    first = children[0]
    if isinstance(first, list):
        return frozenset(first)
    if isinstance(first, frozenset):
        return first
    return frozenset(str(child) for child in children if child is not None)


class _ConstraintDeclarationTransformer(Transformer):
    def __init__(self, program: Program):
        super().__init__()
        self.program = program

    def type_name(self, children: list[Any]) -> type:
        return TypeSystem.str_to_type(str(children[0]))

    def type_list(self, children: list[Any]) -> list[type]:
        return list(children)

    def constraint_declaration(self, children: list[Any]) -> None:
        name = str(children[0])
        type_list = children[1]
        self.program.constraint(name, list(type_list) if type_list else [])


@v_args(meta=True)
class RuleTransformer(Transformer):
    def __init__(
        self,
        source: str,
        program: Program,
        *,
        hold_compile: bool = False,
    ):
        super().__init__()
        self.source = source
        self.program = program
        self.hold_compile = hold_compile
        self.rules: list[Rule] = []

    def _source_of(self, meta: Meta) -> str:
        return self.source[meta.start_pos : meta.end_pos]

    def pragma_h_value(self, _meta: Meta, children: list[Any]) -> str:
        return str(children[0])

    def pragma_h_list(self, _meta: Meta, children: list[Any]) -> list[str]:
        return list(children)

    def pragmas_h(self, _meta: Meta, children: list[Any]) -> frozenset[str]:
        return _flatten_pragmas(children)

    def pragmas_r(self, _meta: Meta, children: list[Any]) -> frozenset[str]:
        return frozenset({"catch_failure"}) if children else frozenset()

    def arg_expr(self, meta: Meta, _children: list[Any]) -> Expression:
        return translate_expression(self._source_of(meta))

    def arg_list(
        self, _meta: Meta, children: list[Any]
    ) -> tuple[Expression, ...]:
        return tuple(children)

    def guard_expr(self, meta: Meta, _children: list[Any]) -> Guard:
        return translate_guard(self._source_of(meta))

    def guard_constraints(
        self, _meta: Meta, children: list[Any]
    ) -> tuple[Guard, ...]:
        return tuple(children)

    def guard(self, _meta: Meta, children: list[Any]) -> Guard | None:
        if not children:
            return None

        guards = children[0]
        if len(guards) == 1:
            return guards[0]

        return And(*guards)

    def constraint(self, _meta: Meta, children: list[Any]) -> Constraint:
        name = str(children[0])
        args = children[1]
        return Constraint(name, *(args or ()))

    def head_constraint(self, meta: Meta, children: list[Any]) -> Constraint:
        constraint, pragmas = children
        if constraint.name not in self.program._store_map:
            raise UnknownConstraintError(constraint.name, meta)
        if pragmas:
            constraint.pragma = _format_pragmas(pragmas)
        return constraint

    def head(self, _meta: Meta, children: list[Any]) -> list[Constraint]:
        return list(children)

    def body_atom(
        self, _meta: Meta, children: list[Any]
    ) -> Constraint | FunctionCall:
        constraint, pragmas = children

        item: Constraint | FunctionCall
        if constraint.name in self.program._store_map:
            item = constraint
        else:
            item = FunctionCall(constraint.name, *constraint.args)

        if pragmas:
            if isinstance(item, FunctionCall):
                raise ValueError(
                    "Cannot apply pragmas to an undeclared callback "
                    f"'{item.name}'"
                )
            item.pragma = _format_pragmas(pragmas)

        return item

    def body_literal_value(
        self, _meta: Meta, children: list[Any]
    ) -> Literal["success", "failure"]:
        value = str(children[0])
        if value in {"true", "success"}:
            return "success"
        return "failure"

    def body_literal(
        self, _meta: Meta, children: list[Any]
    ) -> Success | Failure:
        return SUCCESS if children[0] == "success" else FAILURE

    def unification(self, _meta: Meta, children: list[Any]) -> Unification:
        return Unification(children[0], children[1])

    def body_constraint(
        self, _meta: Meta, children: list[Any]
    ) -> list[Constraint | FunctionCall | Success | Failure | Unification]:
        child = children[0]
        return child if isinstance(child, list) else [child]

    def body_constraints(
        self, _meta: Meta, children: list[Any]
    ) -> list[Constraint | FunctionCall | Success | Failure | Unification]:
        items: list[
            Constraint | FunctionCall | Success | Failure | Unification
        ] = []
        for child in children:
            if isinstance(child, list):
                items.extend(child)
            else:
                items.append(child)
        return items

    def body(
        self, _meta: Meta, children: list[Any]
    ) -> list[Constraint | FunctionCall | Success | Failure | Unification]:
        return children[0]

    def propagation_rule(
        self, _meta: Meta, children: list[Any]
    ) -> PropagationRule:
        head, guard, body = children
        return PropagationRule(positive_head=head, guard=guard, body=body)

    def propagation_rule_noh(
        self, _meta: Meta, children: list[Any]
    ) -> PropagationRule:
        head, guard, body = children
        return PropagationRule(positive_head=head, guard=guard, body=body)

    def simplification_rule(
        self, _meta: Meta, children: list[Any]
    ) -> SimplificationRule:
        head, guard, body = children
        return SimplificationRule(negative_head=head, guard=guard, body=body)

    def simpagation_rule(
        self, _meta: Meta, children: list[Any]
    ) -> SimpagationRule:
        positive_head, negative_head, guard, body = children
        return SimpagationRule(
            positive_head=positive_head,
            negative_head=negative_head,
            guard=guard,
            body=body,
        )

    def rule_name(self, _meta: Meta, children: list[Any]) -> str:
        return str(children[0])

    def chr_rule(self, _meta: Meta, children: list[Any]) -> Rule:
        name, rule = children
        if not isinstance(rule, Rule):
            raise TypeError(f"Expected a Rule, got {type(rule).__name__}")
        if name is not None:
            rule.name = name

        self.program.add_rule(rule, hold_compile=self.hold_compile)
        self.rules.append(rule)
        return rule

    def start(self, _meta: Meta, _children: list[Any]) -> list[Rule]:
        return self.rules
