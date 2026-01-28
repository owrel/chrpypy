from itertools import count
from typing import Any

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

AcceptedHeadType = list[Constraint] | Constraint | None
AcceptedBodyType = (
    list[Constraint | Success | Failure | FunctionCall | Unification]
    | FunctionCall
    | Constraint
    | Success
    | Failure
    | Unification
    | None
)
HeadType = list[Constraint]
GuardType = Guard | list[Guard] | set[Guard] | None
BodyType = list[Constraint | Success | Failure | FunctionCall | Unification]


def _normalize_list(item: Any) -> list[Constraint]:
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
        self.name = name
        self.positive_head = positive_head or []
        self.negative_head = negative_head or []
        self.guard = guard
        self.body = body or []
        self._id = next(Rule._rule_counter)

    def with_name(self, name: str) -> "Rule":
        self.name = name
        return self

    def _format_body(self) -> str:
        if not self.body:
            return "true"
        if len(self.body) == 1 and isinstance(self.body[0], (Success, Failure)):
            return str(self.body[0])

        return ", ".join(str(c) for c in self.body)

    def to_str(self) -> str:
        if not (self.positive_head or self.negative_head):
            raise ValueError(
                "Rule must have either a positive head or a negative head"
            )

        name_prefix = self.name or f"Rule{self._id}"

        guard_str = f" {self.guard} |" if self.guard else ""
        body_str = self._format_body()

        positive_str = ", ".join(str(c) for c in self.positive_head)

        if not self.negative_head:
            return f"{name_prefix} @ {positive_str} ==> {guard_str} {body_str}"

        if not self.positive_head:
            return f"{name_prefix} @ {', '.join(str(c) for c in self.negative_head)} <=> {guard_str} {body_str}"

        negative_str = ", ".join(str(c) for c in self.negative_head)
        return f"{name_prefix} @ {positive_str} \\ {negative_str} <=> {guard_str} {body_str}"

    def get_all_constraints(self) -> list[Constraint]:
        constraints = []
        constraints.extend(self.positive_head)
        constraints.extend(self.negative_head)
        constraints.extend([c for c in self.body if isinstance(c, Constraint)])
        return constraints


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
