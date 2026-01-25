from dataclasses import field
from typing import TYPE_CHECKING, Any

from .expressions import Constant, Expression, Variable, ensure_expr
from .typesystem import TypeSystem

if TYPE_CHECKING:
    from .program import Program


class Constraint:
    name: str
    args: list["Expression"] = field(default_factory=list)

    def __init__(self, *args: Any):
        if self.__class__.__name__ == "Constraint":
            if len(args) > 0:
                self.name = args[0]
                args = args[1:]
        else:
            self.name = self.__class__.__name__

        self.args = [ensure_expr(arg) for arg in args]

    def __repr__(self):
        if not self.args:
            return f"{self.name}()"
        args_str = ", ".join(str(arg) for arg in self.args)
        return f"{self.name}({args_str})"

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

            if isinstance(expr, Variable):
                raise TypeError(
                    "Found variables in constraint that supposed to be grounded, check for bugs in is_grounded()"
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


class ConstraintStore:
    def __init__(
        self,
        name: str,
        program: "Program",
        types: tuple[Any] | list[Any] | None = None,
    ):
        self.name = name
        self.program = program

        if types is None:
            types = []

        for t in types:
            if t not in TypeSystem.python_types():
                raise ValueError(
                    f"{t} is not recognize as handled type. Handled types : {TypeSystem.python_types()}"
                )
        self.types = types
        self.history: list[Constraint] = []

    def __call__(self, *args: Any) -> Constraint:
        ret = Constraint()
        ret.name = self.name
        ret.set_args(*args)
        self.history.append(ret)
        return ret

    def post(self, *args: Any) -> None:
        self.program.post(self(*args))

    def get(self) -> list[Constraint]:
        return [
            c for c in self.program.get_constraints() if c.name == self.name
        ]

    def from_chr_string(self, input: str) -> "Constraint":
        name = input[: input.find("#")]
        args = input[input.find("(") + 1 : -1].split(",")

        return Constraint(
            name,
            *[
                TypeSystem.cast(arg, self.types[idx])
                for idx, arg in enumerate(args)
            ],
        )
