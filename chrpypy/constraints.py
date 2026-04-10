import logging
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

logger = logging.getLogger(__name__)


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
        if self.pragma:
            return f"{self.name}({args_str})#{self.pragma}"
        return f"{self.name}({args_str})"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def arity(self) -> int:
        return len(self.args)

    def set_args(self, *args: Any) -> None:
        self.args = [ensure_expr(arg) for arg in args]

    def is_grounded(self) -> bool:
        return all(
            expr.is_grounded() for expr in self.args if isinstance(expr, Symbol)
        )

    def extract_values(self) -> list[Any]:
        if not self.is_grounded():
            raise ValueError(
                "Constraint that is not grounded can not have its values extracted"
            )

        def rec_extract_values(expr: Expression) -> list[Any]:
            if isinstance(expr, LogicalVariable):
                return [expr]

            if isinstance(expr, Constant):
                return [expr.value]

            if isinstance(expr, Symbol):
                raise TypeError(
                    "Found symbol in constraint that supposed to be grounded, check for bugs in is_grounded()"
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
        yield from self.extract_values()


class ConstraintStore:
    def __init__(
        self,
        name: str,
        program: "Program",
        types: tuple[Any] | list[Any] | None = None,
        *,
        lazy: bool = True,
    ):

        self.types: list[Any]
        self.name = name
        self.program = program
        self._cache = []
        self.history: list[Constraint] = []

        if self.name == self.program.name:
            raise ValueError(
                f"Constraint {name} can not have the same name as program {name}"
            )

        if not types:
            self.types = []
            if lazy:
                if isinstance(types, list):
                    self.initialized = True
                else:
                    self.initialized = False
            else:
                self.initialized = True
        else:
            for idx, arg in enumerate(types):
                if arg is None or arg not in TypeSystem.python_types():
                    raise TypeError(
                        f"Argument {idx + 1} of constraint '{self.name}' has incompatible type. "
                        f"Expected {TypeSystem.python_types()}, got {arg} of type {type(arg)}"
                    )

            one_none = any(True if t is None else False for t in types)  # noqa
            if one_none:
                if lazy:
                    self.initialized = False
                    self.handle_lazy_init(list(types))
                else:
                    raise ValueError(
                        f"Found uninitialized value {types} but it is not lazy init"
                    )
            else:
                self.initialized = True
                self.types = list(types)
                self.program._set_reset_systems(self)

    def handle_lazy_init(self, args: list[Any]) -> None:
        if self.initialized:
            logger.warning(
                "Calling handle lazy init with already initialized constraint store types"
            )
            return

        if len(self.types) <= 0:
            self.types = [None for _ in range(len(args))]
        else:
            for idx, (arg, expected_type) in enumerate(
                zip(args, self.types, strict=True)
            ):
                if expected_type is None:
                    if not isinstance(
                        arg, (Expression, *TypeSystem.python_types())
                    ):
                        raise TypeError(
                            f"Argument {idx + 1} of constraint '{self.name}' has incompatible type. "
                            f"Expected {(Expression, *TypeSystem.python_types())}, got {type(arg).__name__}"
                        )
                    if isinstance(arg, Constant):
                        self.types[idx] = type(arg.value)

                    elif isinstance(arg, (*TypeSystem.python_types(),)):
                        self.types[idx] = type(arg)
                    else:
                        print(type(arg))

                else:
                    if not isinstance(
                        arg, (Expression, *TypeSystem.python_types())
                    ):
                        raise TypeError(
                            f"Argument {idx + 1} of constraint '{self.name}' has incompatible type for checking. "
                            f"Expected {(Expression, *TypeSystem.python_types())}, got {type(arg).__name__}"
                        )

                    if isinstance(arg, Constant):
                        if type(self.types[idx]) is not type(arg.value):
                            raise TypeError(
                                f"Argument {idx + 1} of constraint '{self.name}' has incompatible type for checking. "
                                f"Expected {type(self.types[idx])}, got {type(arg.value)}"
                            )

                    elif isinstance(arg, *TypeSystem.python_types()):
                        if type(self.types[idx]) is not type(arg):
                            raise TypeError(
                                f"Argument {idx + 1} of constraint '{self.name}' has incompatible type for checking. "
                                f"Expected {type(self.types[idx])}, got {type(arg)}"
                            )

                    else:
                        print(type(arg))

        one_none = any(True if t is None else False for t in self.types)  # noqa
        print(one_none, not one_none)
        if not one_none:
            self.initialized = True
            print(self.initialized)
            self.program._set_reset_systems(self)

    def __call__(self, *args: Any, pragma: str | None = None) -> Constraint:
        if not self.initialized:
            self.handle_lazy_init(list(args))

        if self.initialized and len(self.types) > 0:
            if len(args) != len(self.types):
                raise ValueError(
                    f"Constraint '{self.name}' expects {len(self.types)} arguments but got {len(args)}"
                )

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

    def post(self, *args: Any) -> list[Constraint]:
        if not self.initialized:
            self.handle_lazy_init(list(args))
        c = self(*args)
        self.program.post(c)
        self._cache = []
        return self.program.store()

    def posts(self, argss: list[Any]) -> list[Constraint]:
        c_list = []
        for args in argss:
            c = self(*args)
            c_list.append(c)
        for c in c_list:
            self.program.post(c)
        self._cache = []
        return self.program.store()

    def get(self) -> list[Constraint]:
        if self._cache:
            return self._cache

        self._cache = [c for c in self.program.store() if c.name == self.name]
        return self._cache

    def from_chr_string(self, input: str) -> Constraint:
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

    def is_initialized(self) -> bool:
        return self.initialized

    def __str__(self) -> str:
        if self.program._compiler.wrapper is not None:
            cs_content = ", ".join(str(c) for c in self.get())
        else:
            cs_content = "~[]"

        return f"{self.name}({', '.join(t.__name__ if t is not None else str(t) for t in self.types)}) : {cs_content}"

    def __repr__(self) -> str:
        return self.__str__()

    def _get_associated_reset_constraint_name(self) -> str:
        return f"reset{self.name}"

    def reset(self) -> list[Constraint]:
        self.program._store_map[
            self._get_associated_reset_constraint_name()
        ].post()
        return self.get()
