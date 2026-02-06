from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Any

from .expressions import (
    Constant,
    Expression,
    LogicalVariable,
    Symbol,
    ensure_expr,
)
from .typesystem import TypeSystem

if TYPE_CHECKING:
    from .program import Program


class ConstraintOrigin(Enum):
    CHRPP = "CHRPP"
    PYTHON = "PYTHON"


class Constraint:
    def __init__(self, *args: Any):
        if self.__class__.__name__ == "Constraint":
            if len(args) > 0:
                self.name = args[0]
                args = args[1:]
        else:
            self.name = self.__class__.__name__

        self.args = [ensure_expr(arg) for arg in args]
        self.pragma: str | None = None
        self._origin: ConstraintOrigin = ConstraintOrigin.PYTHON

    @property
    def origin(self) -> ConstraintOrigin:
        return self._origin

    def __repr__(self):
        if not self.args:
            return f"{self.name}()"
        args_str = ", ".join(str(arg) for arg in self.args)
        return f"{self.name}({args_str})#{self.pragma}"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def arity(self) -> int:
        return len(self.args)

    def set_args(self, *args: Any) -> None:
        self.args = [ensure_expr(arg) for arg in args]

    def is_grounded(self) -> bool:
        return all(expr.is_grounded() for expr in self.args)

    def extract_values(self) -> list[Any]:
        if not self.is_grounded():
            raise ValueError(
                "Constraint that is not grounded can not have its values extracted"
            )

        def rec_extract_values(expr: Expression) -> list[Any]:
            if isinstance(expr, Constant):
                return [expr.value]

            if isinstance(expr, (LogicalVariable, Symbol)):
                raise TypeError(
                    "Found variables/symbol in constraint that supposed to be grounded, check for bugs in is_grounded()"
                )

            if len(expr.children()) == 0:
                raise ValueError(
                    f"Expression {expr} is malconstructed, not chilld but is not considered as terminaison expression (Constant or Variables)"
                )

            ret: list[Any] = []
            for child in expr.children():
                ret.extend(rec_extract_values(child))
            return ret

        ret = []
        for arg in self.args:
            ret.extend(rec_extract_values(arg))

        return ret

    def __iter__(self) -> Generator[Any]:
        values = self.extract_values()
        yield from values


class ConstraintStore:
    def __init__(
        self,
        name: str,
        program: "Program",
        types: tuple[Any] | list[Any] | None = None,
    ):
        self.name = name
        self.program = program
        self._cache = []

        if self.name == self.program.name:
            raise ValueError(
                f"Constraint {name} can not have the same name as program {name}"
            )

        if types is None:
            types = []

        for t in types:
            if t not in TypeSystem.python_types():
                raise ValueError(
                    f"{t} is not recognize as handled type. Handled types : {TypeSystem.python_types()}"
                )
        self.types = types
        self.history: list[Constraint] = []

    def __call__(self, *args: Any, pragma: str | None = None) -> Constraint:
        if len(self.types) > 0 and len(args) != len(self.types):
            raise ValueError(
                f"Constraint '{self.name}' expects {len(self.types)} arguments but got {len(args)}"
            )

        if len(self.types) > 0:
            for idx, (arg, expected_type) in enumerate(
                zip(args, self.types, strict=True)
            ):
                if not isinstance(arg, Expression) and not isinstance(
                    arg, expected_type
                ):
                    raise TypeError(
                        f"Argument {idx + 1} of constraint '{self.name}' has incompatible type. "
                        f"Expected {expected_type}, got {type(arg).__name__}"
                    )

        ret = Constraint()
        ret.name = self.name
        ret.set_args(*args)
        ret.pragma = pragma

        self.history.append(ret)
        return ret

    def post(self, *args: Any) -> Constraint:
        c = self(*args)
        self.program.post(c)
        return c

    def get(self) -> list[Constraint]:
        if self._cache:
            return self._cache

        self._cache = [
            c for c in self.program.get_constraints() if c.name == self.name
        ]
        return self._cache

    def from_chr_string(self, input: str) -> "Constraint":
        name = input[: input.find("#")]
        args = input[input.find("(") + 1 : -1].split(",")
        if len(self.types) == 0:
            return Constraint(name)
        return Constraint(
            name,
            *[
                TypeSystem.cast(arg, self.types[idx])
                for idx, arg in enumerate(args)
            ],
        )

    def reset_cache(self) -> None:
        self._cache = []
