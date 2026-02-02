import hashlib
import operator
import os
import shutil
import subprocess
import sysconfig
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from importlib import util
from pathlib import Path
from typing import Any

import pybind11

from .chrgen import CHRGenerator
from .constraints import Constraint, ConstraintStore
from .expressions import FunctionCall
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


class VerboseLevel(Enum):
    QUIET = 0
    INFO = 1
    DEBUG = 2


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

    python_registry_path = str(
        (
            Path(chrpp_path).resolve() / "misc" / "python_callback_registry.hh"
        ).resolve()
    )

    def __init__(
        self,
        name: str | None = None,
        folder: Path | str | None = None,
        verbose: VerboseLevel | str = VerboseLevel.QUIET,
        *,
        use_cache: bool = True,
        compile_on: CompileTrigger | str = CompileTrigger.FIRST_POST,
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
        self.wrapper = None
        self.constraint_stores: dict[str, ConstraintStore] = {}
        self.use_cache = use_cache
        self.max_history = max_history
        self.current_hash_folder: Path | None = None

        if isinstance(verbose, str):
            verbose = verbose.lower()
            if verbose == "quiet":
                self.verbose = VerboseLevel.QUIET
            elif verbose == "info":
                self.verbose = VerboseLevel.INFO
            elif verbose == "debug":
                self.verbose = VerboseLevel.DEBUG
            else:
                raise ValueError(f"Invalid verbose level: {verbose}")
        else:
            self.verbose = verbose

        if isinstance(compile_on, str):
            compile_on = compile_on.lower()
            if compile_on == "first_post":
                self.compile_on = CompileTrigger.FIRST_POST
            elif compile_on == "rule":
                self.compile_on = CompileTrigger.RULE
            elif compile_on == "compile":
                self.compile_on = CompileTrigger.COMPILE
            else:
                raise ValueError(f"Invalid compile trigger: {compile_on}")
        else:
            self.compile_on = compile_on

        self.rules: list[Rule] = []
        self._first_post_done = False

    def _log_info(self, message: str) -> None:
        if self.verbose.value >= VerboseLevel.INFO.value:
            print(f"{message}")

    def _log_debug(self, message: str) -> None:
        if self.verbose.value >= VerboseLevel.DEBUG.value:
            print(f"[DEBUG] {message}")

    def _compute_rules_hash(self) -> str:
        hash_obj = hashlib.sha256()
        for rule in self.rules:
            hash_obj.update(rule.to_str().encode("utf-8"))
        return hash_obj.hexdigest()

    def _check_cached_compilation(self) -> tuple[bool, str]:
        current_hash = self._compute_rules_hash()
        hash_folder = self.folder / current_hash

        if hash_folder.exists():
            target_so = hash_folder / f"{self.name}.so"
            if target_so.exists():
                self._log_debug(
                    f"Found cached compilation for hash: {current_hash}"
                )
                return True, current_hash

        return False, current_hash

    def _cleanup_old_history(self) -> None:
        if not self.folder.exists():
            return

        hash_dirs = [
            (d, d.stat().st_mtime) for d in self.folder.iterdir() if d.is_dir()
        ]

        hash_dirs.sort(key=operator.itemgetter(1))

        while len(hash_dirs) > self.max_history:
            oldest_dir, _ = hash_dirs.pop(0)
            self._log_debug(f"Removing old hash entry: {oldest_dir.name}")
            shutil.rmtree(oldest_dir)

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
            self.compile()
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

    def constraint_store(
        self, name: str, types: list[Any] | tuple[Any, ...] | None = None
    ) -> ConstraintStore:
        if name in self.constraint_stores:
            raise ValueError(
                f"Trying to re_attribute constraint store : '{name}'"
            )

        self.constraint_stores[name] = ConstraintStore(name, self, types)

        return self.constraint_stores[name]

    def import_wrapper(self) -> Any:
        if not self.compiled:
            raise ValueError(
                "Program is not compiled, add rule to compile the object"
            )

        if self.current_hash_folder is None:
            raise ValueError("Current hash folder is not set")

        target = (self.current_hash_folder / f"{self.name}.so").resolve()
        if not target.exists():
            raise ValueError(
                f"FATAL : Could not import target wrapper {target} "
            )

        self._log_debug(f"Importing wrapper from {target}")

        spec = util.spec_from_file_location(self.name, target)
        if spec is None:
            raise ValueError(
                "Unknown error, probably a naming error or pybind11 binding error"
            )
        module = util.module_from_spec(spec)
        if spec.loader is None:
            raise ValueError(
                "Unknown error part 2, probably a naming error or pybind11 binding error"
            )
        spec.loader.exec_module(module)

        return getattr(module, self.name)()

    def post(self, constraint: Constraint) -> None:
        if (
            not self._first_post_done
            and self.compile_on == CompileTrigger.FIRST_POST
        ):
            if not self.compiled:
                self.compile()
                self.compiled = True
            self._first_post_done = True

        if hasattr(
            self.wrapper,
            f"add_{constraint.name}",
        ):
            self.statistics.calls += 1
            start_execution_time = time.time()

            values = constraint.extract_values()

            # eval(f"self.wrapper.add_{constraint.name}({' ,'.join([str(arg) for arg in constraint.args])})")

            getattr(self.wrapper, f"add_{constraint.name}")(
                *(
                    TypeSystem.cast(
                        value,
                        self.constraint_stores[constraint.name].types[idx],
                    )
                    for idx, value in enumerate(values)
                )
            )

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
        if not self.wrapper:
            raise RuntimeError(
                "Registering function require that the program is compiled first"
            )
        if hasattr(self.wrapper, "register_function"):
            getattr(self.wrapper, "register_function")(name, callback)  # noqa
        else:
            raise RuntimeError("Did not find register function in wrapper")

    def get_constraints(self) -> list[Constraint]:
        if self.wrapper is None:
            raise ValueError("Wrapper is None, cannot get constraints")

        list_str_constraint: list[str] = sorted(
            self.wrapper.get_constraint_store()
        )
        return [
            self.constraint_stores[
                constraint[: constraint.find("#")]
            ].from_chr_string(constraint)
            for constraint in list_str_constraint
        ]

    def get_constraint_types(self, name: str) -> list:
        cs = self.constraint_stores[name]
        if cs.types is None:
            return []
        return list(cs.types)

    def _extract_files(self, chrpp_file: Path) -> list[Path]:
        cmd = [self.chrpp_extract_files, str(chrpp_file)]
        self._log_debug(f"Extracting files with command: {' '.join(cmd)}")
        try:
            res = subprocess.run(
                cmd, check=True, capture_output=True, text=True
            ).stdout
        except Exception as e:
            raise RuntimeError(f"Failed to extract files: {e}") from e
        res = res.split(";")
        if not self.current_hash_folder:
            raise RuntimeError(
                "An error has occured : hash folder is not initialized"
            )

        extracted = [self.current_hash_folder / r for r in res]
        self._log_debug(f"Extracted files: {extracted}")
        return extracted

    def compile(self) -> None:
        self._log_debug("Starting compilation process")
        time_lap = time.time()

        self._log_debug("Verifying if paths exist...")
        required_paths = {
            "chrpp_path": Path(self.chrpp_path),
            "chrppc_path": Path(self.chrppc_path),
            "chrpp_runtime": Path(self.chrpp_runtime),
            "chrpp_extract_files": Path(self.chrpp_extract_files),
            "python_registry": Path(self.python_registry_path),
        }

        for name, path in required_paths.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Required path '{name}' does not exist: {path}"
                )
            self._log_debug(f"Verified {name}: {path}")

        self._log_debug("Setting up build directory")
        if not self.folder.exists():
            self.folder.mkdir(parents=True)

        cache_exists, current_hash = self._check_cached_compilation()

        if self.use_cache and cache_exists:
            self._log_info(
                f"Found cached compilation with matching rules hash: {current_hash}"
            )
            self.current_hash_folder = self.folder / current_hash
            self.compiled = True
            mist_start = time.time()
            self.wrapper = self.import_wrapper()
            mist_end = time.time()
            self.statistics.misc_time += mist_end - mist_start
            self._log_debug("Using cached compilation")
            return

        self.current_hash_folder = self.folder / current_hash

        if self.current_hash_folder.exists():
            shutil.rmtree(self.current_hash_folder)
        self.current_hash_folder.mkdir(parents=True, exist_ok=True)

        self._log_debug(f"Building in hash folder: {self.current_hash_folder}")

        if not self.current_hash_folder.is_dir():
            raise ValueError("Hash folder must be a directory")
        self.statistics.misc_time += time.time() - time_lap

        chrpp_gen_start = time.time()

        self._log_info("Generating CHRPP file")
        chr_gen = CHRGenerator(self)
        generated_chrpp_path = (
            self.current_hash_folder / f"{self.name}-pychr.chrpp"
        )

        chr_gen.generate_chrpp_file(generated_chrpp_path)

        self._log_debug(f"Generated CHRPP file at {generated_chrpp_path}")

        chrpp_gen_end = time.time()
        self.statistics.generation_time += chrpp_gen_end - chrpp_gen_start

        chrpp_compile_start = time.time()

        self._log_info("Compiling CHRPP file")
        cmd = [
            self.chrppc_path,
            str(generated_chrpp_path),
            "-o",
            str(self.current_hash_folder),
        ]
        self._log_debug(f"CHRPP compiler command:\n {' '.join(cmd)}")
        try:
            subprocess.run(
                cmd,
                check=True,
            )
        except Exception as e:
            chrpp_end = time.time()
            self.statistics.chrppc_compilation_time += (
                chrpp_end - chrpp_compile_start
            )
            raise RuntimeError(
                f"CHRPP compilation failed with error: {e}"
            ) from e

        chrpp_end = time.time()
        self.statistics.chrppc_compilation_time += (
            chrpp_end - chrpp_compile_start
        )

        wrapper_start = time.time()

        self._log_info("Generating bindings file")
        bindings_path = self.current_hash_folder / f"{self.name}_bindings.cpp"
        chr_gen.generate_bindings_file(bindings_path)
        self._log_debug(f"Generated bindings file at {bindings_path}")

        wrapper_end = time.time()
        self.statistics.generation_time += wrapper_end - wrapper_start

        so_start = time.time()

        include_source = [
            str(p) for p in self._extract_files(generated_chrpp_path)
        ]

        if self._retrieve_callbacks():
            include_source.append(str(self.python_registry_path))

        self._log_info("Compiling C++ shared library")

        cmd = [
            shutil.which("g++"),
            "-shared",
            "-fPIC",
            *include_source,
            str(bindings_path),
            "-I",
            self.chrpp_runtime,
            "-I",
            sysconfig.get_paths()["include"],
            "-I",
            pybind11.get_include(),
            "-o",
            str(self.current_hash_folder / f"{self.name}.so"),
            "-fuse-ld=mold",
            "-std=c++17",
        ]

        self._log_debug(f"C++ compiler command:\n {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            so_end = time.time()
            self.statistics.cpp_compilation_time += so_end - so_start
            raise RuntimeError(f"C++ compilation failed with error: {e}") from e

        so_end = time.time()
        self.statistics.cpp_compilation_time += so_end - so_start
        self.statistics.compiles += 1
        self.compiled = True

        self._cleanup_old_history()

        self._log_debug("Importing wrapper module")
        mist_start = time.time()
        self.wrapper = self.import_wrapper()
        mist_end = time.time()
        self.statistics.misc_time += mist_end - mist_start

        self._log_debug("Compilation process completed successfully")
