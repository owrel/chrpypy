from itertools import count
from typing import Any, TypeAlias

from .constraints import Constraint
from .expressions import (
    And,
    Failure,
    FunctionCall,
    Guard,
    Or,
    Success,
    Unification,
)

AcceptedHeadType: TypeAlias = list[Constraint] | Constraint | None
AcceptedBodyType: TypeAlias = (
    list[Constraint | Success | Failure | FunctionCall | Unification | bool]
    | FunctionCall
    | Constraint
    | Success
    | Failure
    | Unification
    | bool
    | None
)
HeadType: TypeAlias = list[Constraint]
GuardType: TypeAlias = Guard | list[Guard] | set[Guard] | None
BodyType: TypeAlias = list[
    Constraint | Success | Failure | FunctionCall | Unification
]


def format_constraint(constraint: Constraint) -> str:
    if not constraint.args:
        return f"{constraint.name}()"

    args_str = ", ".join(arg.to_chrpp() for arg in constraint.args)
    if constraint.pragma:
        return f"{constraint.name}({args_str})#{constraint.pragma}"
    return f"{constraint.name}({args_str})"


def format_head(head: HeadType) -> str:
    if head is None:
        return ""

    if isinstance(head, list):
        if not head:
            return ""
        return ", ".join(format_constraint(c) for c in head)

    if isinstance(head, Constraint):
        return format_constraint(head)

    return ""


def format_body(body: BodyType) -> str:
    if len(body) == 0:
        return "success()"

    if isinstance(body, (Success, Failure)):
        return body.to_chrpp()

    if isinstance(body, FunctionCall):
        return body.to_chrpp()

    if isinstance(body, list):
        if not body:
            return "success()"

        formatted_parts = []
        for item in body:
            if isinstance(item, Constraint):
                formatted_parts.append(format_constraint(item))
            elif isinstance(
                item, (Success, Failure, FunctionCall, Unification)
            ):
                formatted_parts.append(item.to_chrpp())

        return ", ".join(formatted_parts)

    if isinstance(body, Constraint):
        return format_constraint(body)

    return "success()"


def _normalize_list(item: Any) -> list[Any]:
    if item is None:
        return []
    if isinstance(item, list):
        return item
    if isinstance(item, tuple):
        return list(item)
    if isinstance(item, Constraint):
        return [item]
    return []


def _normalize_guard(guard: Any) -> "Guard | None":
    if guard is None:
        return None
    if isinstance(guard, list):
        return And(*guard) if guard else None
    if isinstance(guard, set):
        return Or(*guard) if guard else None
    return guard


def _normalize_body(
    body: Any,
) -> BodyType:
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(
        body, (Constraint, Success, Failure, FunctionCall, Unification)
    ):
        return [body]

    return []


class Rule:
    _rule_counter = count()

    def __init__(
        self,
        name: str | None = None,
        positive_head: HeadType | None = None,
        negative_head: HeadType | None = None,
        guard: "Guard | None" = None,
        body: BodyType | None = None,
    ) -> None:
        self._id = next(Rule._rule_counter)
        self.name = name
        self.positive_head = positive_head or []
        self.negative_head = negative_head or []
        self.guard = guard
        self.body = body or []

    def _format_body(self) -> str:
        if not self.body:
            return "true"
        if len(self.body) == 1 and isinstance(self.body[0], (Success, Failure)):
            return str(self.body[0])

        return ", ".join(str(c) for c in self.body)

    def to_str(self) -> str:
        return self.to_chrpp()

    def to_chr(self) -> str:
        if not (self.positive_head or self.negative_head):
            raise ValueError(
                "Rule must have either a positive head or a negative head"
            )
        name_prefix = ""
        if self.name:
            name_prefix = f"{self.name} @ "

        guard_str = f" {self.guard} |" if self.guard else ""
        body_str = self._format_body()

        positive_str = ", ".join(str(c) for c in self.positive_head)

        if not self.negative_head:
            return f"{name_prefix}{positive_str} ==> {guard_str} {body_str}"

        if not self.positive_head:
            return f"{name_prefix}{', '.join(str(c) for c in self.negative_head)} <=> {guard_str} {body_str}"

        negative_str = ", ".join(str(c) for c in self.negative_head)
        return f"{name_prefix}{positive_str} \\ {negative_str} <=> {guard_str} {body_str}"

    def get_all_constraints(self) -> list[Constraint]:
        constraints = []
        constraints.extend(self.positive_head)
        constraints.extend(self.negative_head)
        constraints.extend([c for c in self.body if isinstance(c, Constraint)])
        return constraints

    def to_chrpp(self) -> str:
        rule_str = ""

        if self.name:
            rule_str += f"{self.name} @ "

        if self.negative_head and self.positive_head:
            positive = format_head(self.positive_head)
            negative = format_head(self.negative_head)
            rule_str += f"{positive} \\ {negative} <=> "
        elif self.negative_head and not self.positive_head:
            rule_str += f"{format_head(self.negative_head)} <=> "
        elif self.positive_head:
            rule_str += f"{format_head(self.positive_head)} ==> "

        if self.guard:
            guard_str = self.guard.to_chrpp()
            rule_str += f"{guard_str} | "

        rule_str += format_body(self.body)
        rule_str += ";;\n"

        return rule_str

    def __repr__(self) -> str:
        return self.to_str()


class SimplificationRule(Rule):
    def __init__(
        self,
        negative_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            positive_head=None,
            negative_head=_normalize_list(negative_head),
            guard=_normalize_guard(guard),
            body=_normalize_body(body),
        )


class PropagationRule(Rule):
    def __init__(
        self,
        positive_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            positive_head=_normalize_list(positive_head),
            negative_head=None,
            guard=_normalize_guard(guard),
            body=_normalize_body(body),
        )


class SimpagationRule(Rule):
    def __init__(
        self,
        positive_head: AcceptedHeadType = None,
        negative_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            positive_head=_normalize_list(positive_head),
            negative_head=_normalize_list(negative_head),
            guard=_normalize_guard(guard),
            body=_normalize_body(body),
        )
