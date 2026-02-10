import logging
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .compiler import Compiler
from .constraints import Constraint, ConstraintOrigin, ConstraintStore
from .expressions import FunctionCall, LogicalVariable, Symbol
from .rules import (
    AcceptedBodyType,
    AcceptedHeadType,
    GuardType,
    PropagationRule,
    Rule,
    SimpagationRule,
    SimplificationRule,
)
from .typesystem import TypeSystem
from .utils import setup_logging


class CompileTrigger(Enum):
    FIRST_POST = "first_post"
    RULE = "rule"
    COMPILE = "compile"


@dataclass
class Statistics:
    cpp_compilation_time: float = 0
    chrppc_compilation_time: float = 0
    generation_time: float = 0
    execution_time: float = 0
    last_execution_time: float = 0
    calls: int = 0
    compiles: int = 0
    misc_time: float = 0

    @property
    def total_time(self) -> float:
        return (
            self.cpp_compilation_time
            + self.chrppc_compilation_time
            + self.generation_time
            + self.execution_time
            + self.misc_time
        )


setup_logging()

logger = logging.getLogger(__name__)


class Program:
    _id = 0
    chrpp_path = os.getenv(
        "CHRPP_PATH",
        str((Path(__file__).resolve().parent / "chrpp").resolve()),
    )

    chrppc_path = str(
        (Path(chrpp_path).resolve() / "chrppc" / "chrppc").resolve()
    )

    chrpp_runtime = str((Path(chrpp_path).resolve() / "runtime").resolve())

    chrpp_extract_files = str(
        (Path(chrpp_path).resolve() / "misc" / "chrpp_extract_files").resolve()
    )

    helper_hh = str(
        (Path(chrpp_path).resolve() / "misc" / "helper.hh").resolve()
    )

    helper_core_hh = str(
        (Path(chrpp_path).resolve() / "misc" / "helper_core.hh").resolve()
    )

    compile_trigger = CompileTrigger

    def __init__(
        self,
        name: str | None = None,
        folder: Path | str | None = None,
        *,
        use_cache: bool = True,
        compile_on: CompileTrigger = CompileTrigger.FIRST_POST,
        max_history: int = 50,
    ) -> None:
        self.id = Program._id
        Program._id += 1
        self.statistics = Statistics()
        self.name = name or f"program{Program._id}"
        if folder is None:
            tempdir = tempfile.gettempdir()
            self.folder = Path(tempdir) / "chrpypy" / self.name
        else:
            self.folder = Path(folder).resolve()

        self.compiled = False
        self.constraint_stores: dict[str, ConstraintStore] = {}
        self.logical_variable_registry: dict[str, LogicalVariable] = {}
        self.compiler = Compiler(self, max_history, use_cache=use_cache)

        self.compile_on = compile_on

        self.rules: list[Rule] = []
        self._first_post_done = False

    def _retrieve_callbacks(self) -> list[FunctionCall]:
        ret = []
        for rule in self.rules:
            ret.extend(
                expr for expr in rule.body if isinstance(expr, FunctionCall)
            )

        return ret

    def __call__(
        self, *args: Rule | list[Rule] | tuple[Rule], hold_compile: bool = False
    ):
        for arg in args:
            if isinstance(arg, Rule):
                self.rules.append(arg)
            elif isinstance(arg, (list, tuple)):
                for rule in arg:
                    if not isinstance(rule, Rule):
                        raise TypeError(f"Invalid argument type: {type(rule)}")
                self.rules.extend(arg)
            else:
                raise TypeError(f"Invalid argument type: {type(arg)}")

        if not hold_compile and self.compile_on == CompileTrigger.RULE:
            self.compiler.compile()
            self.compiled = True

    def simplification(
        self,
        negative_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
        *,
        hold_compile: bool = False,
    ) -> SimplificationRule:
        rule = SimplificationRule(
            negative_head=negative_head,
            guard=guard,
            body=body,
            name=name,
        )
        self(rule, hold_compile=hold_compile)
        return rule

    def propagation(
        self,
        positive_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
        *,
        hold_compile: bool = False,
    ) -> PropagationRule:
        rule = PropagationRule(
            positive_head=positive_head,
            guard=guard,
            body=body,
            name=name,
        )
        self(rule, hold_compile=hold_compile)
        return rule

    def simpagation(
        self,
        positive_head: AcceptedHeadType = None,
        negative_head: AcceptedHeadType = None,
        guard: GuardType = None,
        body: AcceptedBodyType = None,
        name: str | None = None,
        *,
        hold_compile: bool = False,
    ) -> SimpagationRule:
        rule = SimpagationRule(
            positive_head=positive_head,
            negative_head=negative_head,
            guard=guard,
            body=body,
            name=name,
        )
        self(rule, hold_compile=hold_compile)
        return rule

    def logicalvar(self, name: str, _type: Any) -> LogicalVariable:

        self.logical_variable_registry[name] = LogicalVariable(
            name, _type, self
        )

        if hasattr(
            self.compiler.wrapper,
            f"set_logical_var_{self.logical_variable_registry[name]._type.__name__}",
        ):
            getattr(
                self.compiler.wrapper,
                f"set_logical_var_{self.logical_variable_registry[name]._type.__name__}",
            )(name)
        else:
            raise TypeError(
                f"Cound not find function to create logical var of type {_type.__name__}"
            )

        return self.logical_variable_registry[name]

    def symbol(self, name: str) -> Symbol:
        return Symbol(name)

    def constraint_store(
        self, name: str, types: list[Any] | tuple[Any, ...] | None = None
    ) -> ConstraintStore:
        if name in self.constraint_stores:
            raise ValueError(
                f"Trying to re_attribute constraint store : '{name}'"
            )

        self.constraint_stores[name] = ConstraintStore(name, self, types)

        return self.constraint_stores[name]

    def post(self, constraint: Constraint) -> None:
        if (
            not self._first_post_done
            and self.compile_on == CompileTrigger.FIRST_POST
        ):
            if not self.compiled:
                self.compiler.compile()
                self.compiled = True
            self._first_post_done = True

        if hasattr(
            self.compiler.wrapper,
            f"add_{constraint.name}",
        ):
            self.statistics.calls += 1
            start_execution_time = time.time()

            values = constraint.extract_values()

            # eval(f"self.wrapper.add_{constraint.name}({' ,'.join([str(arg) for arg in constraint.args])})")

            args = []

            for idx, val in enumerate(values):
                if isinstance(val, LogicalVariable):
                    args.append(val)
                else:
                    args.append(
                        TypeSystem.cast(
                            val,
                            self.constraint_stores[constraint.name].types[idx],
                        )
                    )

            getattr(self.compiler.wrapper, f"add_{constraint.name}")(*args)

            for cs in self.constraint_stores.values():
                cs.reset_cache()

            mem = time.time() - start_execution_time
            self.statistics.execution_time += mem
            self.statistics.last_execution_time = mem
        else:
            raise ValueError(
                f"Constraint {constraint.name} not found, compile the the program with Constraint definition first"
            )

    def register_function(self, name: str, callback: Callable) -> None:
        if not self.compiler.wrapper:
            raise RuntimeError(
                "Registering function require that the program is compiled first"
            )
        if hasattr(self.compiler.wrapper, "register_function"):
            getattr(self.compiler.wrapper, "register_function")(name, callback)  # noqa
        else:
            raise RuntimeError("Did not find register function in wrapper")

    def get_constraints(self) -> list[Constraint]:
        if self.compiler.wrapper is None:
            raise ValueError("Wrapper is None, cannot get constraints")

        list_str_constraint: list[str] = sorted(
            self.compiler.wrapper.get_constraint_store()
        )
        ret = []
        for str_constraint in list_str_constraint:
            constraint = self.constraint_stores[
                str_constraint[: str_constraint.find("#")]
            ].from_chr_string(str_constraint)
            constraint._origin = ConstraintOrigin.CHRPP
            ret.append(constraint)
        return ret

    def get_constraint_types(self, name: str) -> list:
        cs = self.constraint_stores[name]
        if cs.types is None:
            return []
        return list(cs.types)

    def compile(self) -> None:
        self.compiler.compile()

    def print(self, *, chrpp_format: bool = False) -> str:
        if not chrpp_format:
            return "\n".join([rule.to_str() for rule in self.rules])
        return self.compiler.chr_gen.chr_block_generator.generate()
