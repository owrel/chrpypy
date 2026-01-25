from dataclasses import dataclass, field
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
)

AcceptedHeadType = list[Constraint] | Constraint | None
AcceptedBodyType = (
    list[Constraint | Success | Failure | FunctionCall]
    | FunctionCall
    | Constraint
    | Success
    | Failure
    | None
)
HeadType = list[Constraint]
GuardType = Guard | list[Guard] | set[Guard] | None
BodyType = list[Constraint | Success | Failure | FunctionCall]


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
) -> list[Constraint | Success | Failure | FunctionCall]:
    if body is None:
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, (Constraint, Success, Failure, FunctionCall)):
        return [body]
    return []


@dataclass
class Rule:
    name: str | None = None
    positive_head: HeadType = field(default_factory=list)
    negative_head: HeadType = field(default_factory=list)
    guard: "Guard | None" = None
    body: BodyType = field(default_factory=list)
    _id: int = field(default_factory=count().__next__)

    def __post_init__(self) -> None:
        self.positive_head = _normalize_list(self.positive_head)
        self.negative_head = _normalize_list(self.negative_head)
        self.guard = _normalize_guard(self.guard)
        self.body = _normalize_body(self.body)

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
        head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        head_list = _normalize_list(head or [])
        guard_obj = _normalize_guard(guard)
        body_obj = _normalize_body(body)

        self.name = name
        self.positive_head = head_list
        self.negative_head = []
        self.guard = guard_obj
        self.body = body_obj
        self._id = next(count().__next__() for _ in range(1))  # type: ignore


class PropagationRule(Rule):
    def __init__(
        self,
        head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        head_list = _normalize_list(head or [])
        guard_obj = _normalize_guard(guard)
        body_obj = _normalize_body(body)

        self.name = name
        self.positive_head = []
        self.negative_head = head_list
        self.guard = guard_obj
        self.body = body_obj
        self._id = next(count().__next__() for _ in range(1))  # type: ignore


class SimpagationRule(Rule):
    def __init__(
        self,
        positive_head: AcceptedHeadType = None,
        negative_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
    ) -> None:
        pos_head_list = _normalize_list(positive_head or [])
        neg_head_list = _normalize_list(negative_head or [])
        guard_obj = _normalize_guard(guard)
        body_obj = _normalize_body(body)

        self.name = name
        self.positive_head = pos_head_list
        self.negative_head = neg_head_list
        self.guard = guard_obj
        self.body = body_obj
        self._id = next(count().__next__() for _ in range(1))  # type: ignore
