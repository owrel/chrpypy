import logging
import os
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import singledispatchmethod
from pathlib import Path
from types import FunctionType
from typing import Any, Literal, Self, overload

from .compiler import Compiler
from .constraints import Constraint, ConstraintOrigin, ConstraintStore
from .expressions import ANON, FunctionCall, LogicalVariable, Symbol
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
    _chrpp_path = os.getenv(
        "CHRPP_PATH",
        str((Path(__file__).resolve().parent / "chrpp").resolve()),
    )

    _chrppc_path = str(
        (Path(_chrpp_path).resolve() / "chrppc" / "chrppc").resolve()
    )

    _chrpp_runtime = str((Path(_chrpp_path).resolve() / "runtime").resolve())

    _chrpp_extract_files = str(
        (Path(_chrpp_path).resolve() / "misc" / "chrpp_extract_files").resolve()
    )

    _helper_hh = str(
        (Path(_chrpp_path).resolve() / "misc" / "helper.hh").resolve()
    )

    _helper_core_hh = str(
        (Path(_chrpp_path).resolve() / "misc" / "helper_core.hh").resolve()
    )

    compile_trigger = CompileTrigger

    def __init__(
        self,
        name: str | None = None,
        folder: Path | str | None = None,
        *,
        use_cache: bool = True,
        compile_on: Literal["first_post", "rule", "compile"] = "first_post",
        max_history: int = 50,
        auto_reset_rules: bool = True,
    ) -> None:
        self._id = Program._id
        Program._id += 1

        self.name = name or f"program{Program._id}"

        self._auto_reset_rules = auto_reset_rules

        if folder is None:
            tempdir = tempfile.gettempdir()
            self._folder = Path(tempdir) / "chrpypy" / self.name
        else:
            self._folder = Path(folder).resolve()

        self._store_map: dict[str, ConstraintStore] = {}
        self._logical_variable_map: dict[str, LogicalVariable] = {}
        self._compiler = Compiler(self, max_history, use_cache=use_cache)

        if isinstance(compile_on, str):
            self._compile_on = CompileTrigger(compile_on.lower())
        else:
            self._compile_on = compile_on

        self._statistics = Statistics()
        self._rules: list[Rule] = []
        self._rule_counter = 0
        self._reset_stores: list[ConstraintStore] = []
        self._reset_rule_names: set[str] = set()
        self._pending_functions: dict[str, Callable] = {}

    @property
    def statistics(self) -> Statistics:
        return self._statistics

    def _set_reset_systems(self, cs: ConstraintStore) -> None:
        if not cs.initialized and len(cs.types) == 0:
            raise RuntimeError(
                "Can not create reset system while constraint is not inialized"
            )

        if cs._get_associated_reset_constraint_name() in self._store_map:
            raise RuntimeError(
                f"Found a constraint store with reserved name {cs._get_associated_reset_constraint_name()}"
            )
        reset_constraint_store = ConstraintStore(
            cs._get_associated_reset_constraint_name(),
            self,
            [],
            lazy=False,
            with_reset=False,
        )

        self._store_map[reset_constraint_store.name] = reset_constraint_store
        self._reset_stores.append(reset_constraint_store)

        consume_rule = SimpagationRule(
            name=f"{reset_constraint_store.name}_consume",
            positive_head=self._store_map[
                cs._get_associated_reset_constraint_name()
            ](),
            negative_head=cs(*[ANON for _ in range(len(cs.types))]),
        )
        stop_consume_rule = SimplificationRule(
            name=f"{reset_constraint_store.name}_stop_consume",
            negative_head=self._store_map[
                cs._get_associated_reset_constraint_name()
            ](),
        )

        if consume_rule.name is None or stop_consume_rule.name is None:
            raise RuntimeError(
                "consume_rule.name or stop_consume_rule can not be set to none"
            )

        self._reset_rule_names.add(consume_rule.name)
        self._reset_rule_names.add(stop_consume_rule.name)
        self._rules.extend([consume_rule, stop_consume_rule])

    def _retrieve_callbacks(self) -> list[FunctionCall]:
        ret = []
        for rule in self._rules:
            ret.extend(
                expr for expr in rule.body if isinstance(expr, FunctionCall)
            )

        return ret

    def __str__(self) -> str:
        return self.chr()

    def __repr__(self) -> str:
        return self.__str__()

    def _add_rule(self, r: Rule):
        def find_idx(r: Rule, rules: list[Rule]) -> int:
            for idx, rule in enumerate(rules):
                if rule.name == r.name:
                    return idx
            return -1

        if r.name is None:
            r.name = f"rule{self._rule_counter}"
            self._rule_counter += 1
            self._rules.append(r)
        else:
            idx = find_idx(r, self._rules)
            if idx == -1:
                self._rules.append(r)
                self._rule_counter += 1
            else:
                self._rules[idx] = r
                self._rule_counter += 1

    def add_rule(
        self, *args: Rule | list[Rule] | tuple[Rule], hold_compile: bool = False
    ) -> None:
        self._compiler.compiled = False
        for arg in args:
            if isinstance(arg, Rule):
                self._add_rule(arg)

            elif isinstance(arg, (list, tuple)):
                for rule in arg:
                    if not isinstance(rule, Rule):
                        raise TypeError(f"Invalid argument type: {type(rule)}")
                    self._add_rule(rule)

            else:
                raise TypeError(f"Invalid argument type: {type(arg)}")

        if not hold_compile and self._compile_on == CompileTrigger.RULE:
            self._compiler.compile()

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
        self.add_rule(rule, hold_compile=hold_compile)
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
        self.add_rule(rule, hold_compile=hold_compile)
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

        self.add_rule(rule, hold_compile=hold_compile)
        return rule

    def logicalvar(self, name: str, _type: Any) -> LogicalVariable:
        self._logical_variable_map[name] = LogicalVariable(name, _type, self)

        if hasattr(
            self._compiler.wrapper,
            f"set_logical_var_{self._logical_variable_map[name]._type.__name__}",
        ):
            getattr(
                self._compiler.wrapper,
                f"set_logical_var_{self._logical_variable_map[name]._type.__name__}",
            )(name)
        else:
            raise TypeError(
                f"Cound not find function to create logical var of type {_type.__name__}"
            )

        return self._logical_variable_map[name]

    def logicalvars(
        self, names: Sequence[str], _type: Any
    ) -> tuple[LogicalVariable, ...]:
        return tuple(self.logicalvar(name, _type) for name in names)

    def symbol(self, name: str) -> Symbol:
        return Symbol(name)

    def symbols(self, *names: str) -> tuple[Symbol, ...]:
        return tuple(Symbol(name) for name in names)

    def constraint(
        self,
        name: str,
        types: list[Any] | tuple[Any, ...] | None = None,
        *,
        lazy: bool = True,
    ) -> ConstraintStore:
        if name in self._store_map:
            raise ValueError(
                f"Trying to re_attribute constraint store : '{name}'"
            )
        self._store_map[name] = (
            c := ConstraintStore(name, self, types, lazy=lazy)
        )

        return c

    def post(self, constraint: Constraint) -> None:
        if (
            not self._compiler.compiled
            and self._compile_on == CompileTrigger.FIRST_POST
        ):
            self._compiler.compile()

        if not self._compiler.compiled:
            raise ValueError("Cannot post without a compiled program")

        if self.failed():
            raise RuntimeError("Program is in failure state ; cannot post")

        if hasattr(
            self._compiler.wrapper,
            f"add_{constraint.name}",
        ):
            self._statistics.calls += 1
            start_execution_time = time.time()

            values = constraint.extract_values()

            args = []

            for idx, val in enumerate(values):
                if isinstance(val, LogicalVariable):
                    args.append(val)
                else:
                    args.append(
                        TypeSystem.cast(
                            val,
                            self._store_map[constraint.name].types[idx],
                        )
                    )
            getattr(self._compiler.wrapper, f"add_{constraint.name}")(*args)

            for cs in self._store_map.values():
                cs.reset_cache()

            mem = time.time() - start_execution_time
            self._statistics.execution_time += mem
            self._statistics.last_execution_time = mem
        else:
            raise ValueError(
                f"Constraint {constraint.name} not found, compile the the program with Constraint definition first"
            )

    @overload
    def function(self, callback: Callable, /, *args: Any) -> FunctionCall: ...

    @overload
    def function(
        self, name: str, callback: Callable, /, *args: Any
    ) -> FunctionCall: ...

    @singledispatchmethod
    def function(self, _: Any, /, *args: Any) -> FunctionCall:  # noqa
        raise TypeError(
            f"Expected a string (function name) or a callable, got {type(_).__name__}"
        )

    @function.register
    def _from_callable(
        self, callback: FunctionType, /, *args: Any
    ) -> FunctionCall:
        name: str = callback.__name__
        if name == "<lambda>":
            raise ValueError(
                "Cannot auto-name a lambda, pass an explicit name: "
                'program.function("my_name", lambda ...)'
            )
        self._pending_functions[name] = callback
        if self._compiler.wrapper is not None:
            self._apply_pending_function(name)
        return FunctionCall(name, *args)

    @function.register
    def _from_name(self, name: str, /, *args: Any) -> FunctionCall:
        if not args:
            raise TypeError("function() requires a callback after the name")
        callback = args[0]
        func_args = args[1:]
        self._pending_functions[name] = callback
        if self._compiler.wrapper is not None:
            self._apply_pending_function(name)
        return FunctionCall(name, *func_args)

    def _apply_pending_function(self, name: str) -> None:
        if self._compiler.wrapper is None:
            return
        if hasattr(self._compiler.wrapper, "register_function"):
            getattr(self._compiler.wrapper, "register_function")(  # noqa
                name, self._pending_functions[name]
            )
        else:
            raise RuntimeError("Did not find register function in wrapper")

    def failed(self) -> bool:
        if self._compiler.wrapper is None:
            raise ValueError("Wrapper is None, cannot check failure status")
        return self._compiler.wrapper.failed()

    def reset_program(self) -> None:
        if self._compiler.wrapper is None:
            raise ValueError("Wrapper is None, cannot reset program")
        self._compiler.wrapper.reset_program()

    def store(self) -> list[Constraint]:
        if not self._compiler.compiled:
            raise ValueError("Program is not compiled, cannot access store")

        if self._compiler.wrapper is None:
            raise ValueError("Wrapper is None, cannot access store")

        list_str_constraint: list[str] = sorted(
            self._compiler.wrapper.get_constraint_store()
        )
        ret = []
        for str_constraint in list_str_constraint:
            constraint = self._store_map[
                str_constraint[: str_constraint.find("#")]
            ].from_chr_string(str_constraint)
            constraint._origin = ConstraintOrigin.CHRPP
            ret.append(constraint)
        return ret

    def compile(self) -> Self:
        self._compiler.compile()
        return self

    def chr(self, *, include_reset_rules: bool = False) -> str:
        if include_reset_rules:
            rules = self._rules
        else:
            rules = [
                r for r in self._rules if r.name not in self._reset_rule_names
            ]
        return "\n".join([rule.to_str() for rule in rules])

    def to_chrpp(self, *, include_reset_rules: bool = False) -> str:
        exclude_names = None if include_reset_rules else self._reset_rule_names
        return self._compiler.chr_gen.chr_block_generator.generate(
            exclude_rule_names=exclude_names
        )

    def reset_store(self) -> list[Constraint]:
        for rcs in self._reset_stores:
            rcs.post()
        return self.store()
