import hashlib
import importlib
import logging
import operator
import os
import shlex
import shutil
import subprocess
import sysconfig
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from importlib import util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pybind11

from .chrgen import CHRGenerator
from .constraints import LOGICAL_VAR_RE, Constraint
from .typesystem import TypeSystem

if TYPE_CHECKING:
    from .program import Program

logger = logging.getLogger(__name__)


def _ensure_executable(path: Path) -> None:
    if path.is_file() and not os.access(path, os.X_OK):
        path.chmod(path.stat().st_mode | 0o111)


class Compiler:
    def __init__(
        self,
        program: "Program",
        max_history: int,
        *,
        use_cache: bool,
        traces: bool,
    ) -> None:
        self.program = program
        self.max_history = max_history
        self.use_cache = use_cache
        self.wrapper = None
        self.chr_gen = CHRGenerator(self.program)
        self.compiled = False
        self._unique_module_name: str | None = None
        self.traces = traces

        self.current_hash_folder: Path = (
            Path(tempfile.gettempdir()) / "default _chrpypy_compile"
        )

    def _compute_hash(self) -> str:
        hash_obj = hashlib.sha256(usedforsecurity=False)
        hash_obj.update(self.chr_gen.generate_chrpp().encode("utf-8"))
        hash_obj.update(self.chr_gen.generate_bindings().encode("utf-8"))
        return hash_obj.hexdigest()

    def _check_cached_compilation(self) -> tuple[bool, str]:
        current_hash = self._compute_hash()
        hash_folder = self.program._folder / current_hash
        unique_name = f"{self.program.name}_{current_hash[:16]}"

        if hash_folder.exists():
            target_so = hash_folder / f"{unique_name}.so"
            if target_so.exists():
                logger.debug(
                    f"Found cached compilation for hash: {current_hash}"
                )
                return True, current_hash

        return False, current_hash

    def _cleanup_old_history(self) -> None:
        if not self.program._folder.exists():
            return

        hash_dirs = [
            (d, d.stat().st_mtime)
            for d in self.program._folder.iterdir()
            if d.is_dir()
        ]

        hash_dirs.sort(key=operator.itemgetter(1))

        while len(hash_dirs) > self.max_history:
            oldest_dir, _ = hash_dirs.pop(0)
            logger.debug(f"Removing old hash entry: {oldest_dir.name}")
            shutil.rmtree(oldest_dir)

    def import_wrapper(self) -> Any:
        if not self.compiled:
            raise ValueError(
                "Program is not compiled, add rule to compile the object"
            )

        if self.current_hash_folder is None:
            raise ValueError("Current hash folder is not set")

        if self._unique_module_name is None:
            raise ValueError("Unique module name is not set")

        target = (
            self.current_hash_folder / f"{self._unique_module_name}.so"
        ).resolve()
        if not target.exists():
            raise ValueError(
                f"FATAL : Could not import target wrapper {target} "
            )

        logger.debug(f"Importing wrapper from {target}")

        importlib.invalidate_caches()

        spec = util.spec_from_file_location(self._unique_module_name, target)
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

        wrapper = getattr(module, self._unique_module_name)()
        self.program._register_logical_vars(wrapper)
        return wrapper

    def register_function(self, name: str, callback: Callable) -> None:
        if not self.wrapper:
            raise RuntimeError(
                "Registering function require that the program is compiled first"
            )
        if hasattr(self.wrapper, "register_function"):
            getattr(self.wrapper, "register_function")(name, callback)  # noqa
        else:
            raise RuntimeError("Did not find register function in wrapper")

    def _extract_files(self, chrpp_file: Path) -> list[Path]:
        cmd = [self.program._chrpp_extract_files, str(chrpp_file)]
        logger.debug(f"Extracting files with command: {' '.join(cmd)}")
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

        extracted = [
            self.current_hash_folder / r for r in res if r.endswith(".cpp")
        ]
        logger.debug(f"Extracted files: {extracted}")
        return extracted

    def _handle_compilation_error(self, error: Exception, stage: str) -> None:
        if self.current_hash_folder and self.current_hash_folder.exists():
            error_folder_name = (
                f"compilation_error_{self.current_hash_folder.name}"
            )
            error_folder = self.program._folder / error_folder_name

            if error_folder.exists():
                shutil.rmtree(error_folder)

            self.current_hash_folder.rename(error_folder)
            self.current_hash_folder = error_folder

            error_file = error_folder / "COMPILATION_ERROR"
            error_message = f"{stage} compilation failed with error:\n{error}"
            if (
                isinstance(error, subprocess.CalledProcessError)
                and error.stderr
            ):
                error_message += f"\n\nSubprocess stderr:\n{error.stderr}"
            error_file.write_text(error_message)
            logger.error(f"Compilation error saved to {error_file}")

    def _save_state_for_restore(self) -> dict[str, list[Constraint]]:
        if self.wrapper is None:
            return {}

        builtin_names = (
            self.program._BUILTIN_ACTIVE_NAME,
            self.program._BUILTIN_DEACTIVATE_NAME,
        )
        saved_state: dict[str, list[Constraint]] = {}
        reset_stores = self.program._reset_stores
        for (
            constraint_store_name,
            constraint_store,
        ) in self.program._store_map.items():
            if constraint_store_name in builtin_names:
                continue
            if constraint_store in reset_stores:
                continue
            saved_state[constraint_store_name] = constraint_store.get()
        return saved_state

    def _save_grounded_logical_vars(self) -> dict[str, Any]:
        if self.wrapper is None:
            return {}

        grounded: dict[str, Any] = {}
        for name, logical_var in self.program._logical_variable_map.items():
            raw = logical_var._get_value_raw()
            if LOGICAL_VAR_RE.match(raw.strip()):
                continue
            grounded[name] = TypeSystem.cast(raw, logical_var._type)
        return grounded

    def _restore_grounded_logical_vars(self, grounded: dict[str, Any]) -> None:
        for name, value in grounded.items():
            self.program._logical_variable_map[name].unify(value)

    def _ensure_activation(self) -> None:
        if self.program._builtin_rules_activation and not self.program.failed():
            self.program.activate_rules()

    def _restore_saved_state(
        self, saved_state: dict[str, list[Constraint]]
    ) -> None:
        if not saved_state:
            return

        self.program.suppress_rules()
        try:
            for saved_constraints in saved_state.values():
                for constraint in saved_constraints:
                    if not self.program._constraint_matches_definition(
                        constraint
                    ):
                        continue
                    self.program.post(constraint)
        finally:
            self._ensure_activation()

    def compile(self, *, restore_previous_state: bool) -> None:
        restore_state = (
            restore_previous_state and self.program._builtin_rules_activation
        )
        saved_state = self._save_state_for_restore() if restore_state else {}
        grounded = self._save_grounded_logical_vars() if restore_state else {}

        logger.debug("Starting compilation process")
        time_lap = time.time()

        logger.debug("Verifying if paths exist...")
        required_paths = {
            "chrpp_path": Path(self.program._chrpp_path),
            "chrppc_path": Path(self.program._chrppc_path),
            "chrpp_runtime": Path(self.program._chrpp_runtime),
            "chrpp_extract_files": Path(self.program._chrpp_extract_files),
            "helper_hh": Path(self.program._helper_hh),
        }

        for name, path in required_paths.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Required path '{name}' does not exist: {path}"
                )
            logger.debug(f"Verified {name}: {path}")

        for binary in (
            self.program._chrppc_path,
            self.program._chrpp_extract_files,
        ):
            _ensure_executable(Path(binary))

        logger.debug("Setting up build directory")
        if not self.program._folder.exists():
            self.program._folder.mkdir(parents=True)

        cache_exists, current_hash = self._check_cached_compilation()

        self._unique_module_name = f"{self.program.name}_{current_hash[:16]}"

        if self.use_cache and cache_exists:
            logger.debug(
                f"Found cached compilation with matching rules hash: {current_hash}"
            )
            self.current_hash_folder = self.program._folder / current_hash
            self.compiled = True
            mist_start = time.time()
            self.wrapper = self.import_wrapper()
            mist_end = time.time()
            self.program._statistics.misc_time += mist_end - mist_start
            logger.debug("Using cached compilation")

            self._restore_grounded_logical_vars(grounded)
            for name in list(self.program._pending_functions):
                self.program._apply_pending_function(name)
            self._restore_saved_state(saved_state)
            self._ensure_activation()
            return

        self.current_hash_folder = self.program._folder / current_hash
        log_file = self.current_hash_folder / "compilation.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        def write_to_log(message: str) -> None:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")

        if self.current_hash_folder.exists():
            shutil.rmtree(self.current_hash_folder)
        self.current_hash_folder.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Building in hash folder: {self.current_hash_folder}")
        write_to_log(f"Building in hash folder: {self.current_hash_folder}")

        if not self.current_hash_folder.is_dir():
            raise ValueError("Hash folder must be a directory")
        self.program._statistics.misc_time += time.time() - time_lap

        recompile_script = self.current_hash_folder / "recompile.sh"
        chrpp_file_name = f"{self.program.name}-pychr.chrpp"
        bindings_file_name = f"{self.program.name}_bindings.cpp"
        output_so_name = f"{self._unique_module_name}.so"

        base_dir_quoted = shlex.quote(str(self.program._folder))
        hash_quoted = shlex.quote(current_hash)

        include_flags = [
            "-I",
            '"$BASE_DIR/$HASH"',
            "-I",
            shlex.quote(sysconfig.get_paths()["include"]),
            "-I",
            shlex.quote(self.program._chrpp_runtime),
            "-I",
            shlex.quote(pybind11.get_include()),
        ]
        helper_flag = []
        if self.program._retrieve_callbacks():
            helper_flag = [shlex.quote(str(self.program._helper_hh))]

        with open(recompile_script, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
            f.write("# Recompile script generated by chrpypy\n")
            f.write(
                "# Edit the .chrpp or _bindings.cpp file, then run this script to rebuild\n"
            )
            f.write(f"# Original hash: {current_hash}\n")
            f.write("set -e\n")
            f.write("\n")

            chrppc_bin = shlex.quote(str(self.program._chrppc_path))
            f.write(f"CHRPPC=${{CHRPPC:-{chrppc_bin}}}\n")
            extract_bin = shlex.quote(str(self.program._chrpp_extract_files))
            f.write(f"EXTRACT_FILES=${{EXTRACT_FILES:-{extract_bin}}}\n")
            gpp_bin = shlex.quote("g++")
            f.write(f"GXX=${{GXX:-{gpp_bin}}}\n")
            f.write(f"BASE_DIR={base_dir_quoted}\n")
            f.write(f"HASH=${{HASH:-{hash_quoted}}}\n")
            f.write(f"CHRPP_FILE={shlex.quote(chrpp_file_name)}\n")
            f.write(f"BINDINGS_FILE={shlex.quote(bindings_file_name)}\n")
            f.write(f"OUTPUT_SO={shlex.quote(output_so_name)}\n")
            f.write("\n")

            f.write(
                "# Auto-detect folder: try exact hash first, then compilation_error_ prefix\n"
            )
            f.write('if [ -d "$BASE_DIR/$HASH" ]; then\n')
            f.write('  cd "$BASE_DIR/$HASH"\n')
            f.write('elif [ -d "$BASE_DIR/compilation_error_$HASH" ]; then\n')
            f.write('  cd "$BASE_DIR/compilation_error_$HASH"\n')
            f.write('  HASH="compilation_error_$HASH"\n')
            f.write("else\n")
            f.write(
                '  echo "Error: neither $BASE_DIR/$HASH nor $BASE_DIR/compilation_error_$HASH exist" >&2\n'
            )
            f.write("  exit 1\n")
            f.write("fi")
            f.write("\n")

            f.write("# Step 1: Compile .chrpp file with chrppc\n")
            f.write('"$CHRPPC" "$CHRPP_FILE" -o . --disable-line_error\n')
            f.write("\n")

            f.write("# Step 2: Extract generated C++ source files\n")
            f.write('SOURCES=$("$EXTRACT_FILES" "$CHRPP_FILE" | tr ";" " ")\n')
            f.write("\n")

            f.write("# Step 3: Compile shared library (.so)\n")
            f.write(
                f'"$GXX" -shared -fPIC $SOURCES "$BINDINGS_FILE"'
                f" {' '.join(helper_flag)} {' '.join(include_flags)}"
                f' -o "$OUTPUT_SO" -std=c++17\n'
            )
            f.write("\n")
            f.write('echo "Recompilation successful -> $OUTPUT_SO"\n')

        recompile_script.chmod(0o755)
        write_to_log(f"Recompile script written to {recompile_script}")

        chrpp_gen_start = time.time()

        logger.debug("Generating CHRPP file")
        generated_chrpp_path = (
            self.current_hash_folder / f"{self.program.name}-pychr.chrpp"
        )

        self.chr_gen.generate_chrpp_file(generated_chrpp_path)

        logger.debug(f"Generated CHRPP file at {generated_chrpp_path}")
        write_to_log(f"Generated CHRPP file at {generated_chrpp_path}")

        chrpp_gen_end = time.time()
        self.program._statistics.generation_time += (
            chrpp_gen_end - chrpp_gen_start
        )

        chrpp_compile_start = time.time()

        logger.debug("Compiling CHRPP file")
        chrppc_cmd = [
            self.program._chrppc_path,
            str(generated_chrpp_path),
            "-o",
            str(self.current_hash_folder),
            "--disable-line_error",
        ]
        if self.traces:
            chrppc_cmd.append("--trace")
        logger.debug(f"CHRPP compiler command:\n {' '.join(chrppc_cmd)}")
        write_to_log(f"CHRPP compiler command: {' '.join(chrppc_cmd)}")

        try:
            result = subprocess.run(
                chrppc_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            if result.stdout:
                write_to_log(f"CHRPP compiler output:\n{result.stdout}")
            if result.stderr:
                write_to_log(
                    f"CHRPP compiler warnings/errors:\n{result.stderr}"
                )
        except subprocess.CalledProcessError as e:
            chrpp_end = time.time()
            self.program._statistics.chrppc_compilation_time += (
                chrpp_end - chrpp_compile_start
            )
            write_to_log(f"CHRPP compilation failed with error: {e}")
            if e.stdout:
                write_to_log(f"CHRPP compiler output:\n{e.stdout}")
            if e.stderr:
                write_to_log(f"CHRPP compiler warnings/errors:\n{e.stderr}")
            self._handle_compilation_error(e, "CHRPP")
            error_message = f"CHRPP compilation failed with error:\n{e}\n"
            if e.stderr:
                error_message += f"Details:\n{e.stderr}"
            raise RuntimeError(error_message) from e

        chrpp_end = time.time()
        self.program._statistics.chrppc_compilation_time += (
            chrpp_end - chrpp_compile_start
        )

        wrapper_start = time.time()

        logger.debug("Generating bindings file")

        bindings_path = (
            self.current_hash_folder / f"{self.program.name}_bindings.cpp"
        )
        self.chr_gen.generate_bindings_file(
            bindings_path, module_name=self._unique_module_name
        )
        logger.debug(f"Generated bindings file at {bindings_path}")
        write_to_log(f"Generated bindings file at {bindings_path}")

        wrapper_end = time.time()
        self.program._statistics.generation_time += wrapper_end - wrapper_start

        so_start = time.time()

        sources = [str(p) for p in self._extract_files(generated_chrpp_path)]
        sources.append(str(bindings_path))

        logger.debug("Compiling C++ shared library")
        gpp = shutil.which("g++")
        if gpp is None:
            raise RuntimeError("Could not find g++")

        include_flags = [
            "-I",
            str(self.current_hash_folder),
            "-I",
            sysconfig.get_paths()["include"],
            "-I",
            self.program._chrpp_runtime,
            "-I",
            pybind11.get_include(),
        ]

        so_path = self.current_hash_folder / f"{self._unique_module_name}.so"

        object_files: list[str] = []
        compile_jobs: list[tuple[str, list[str]]] = []
        for source in sources:
            obj = str(Path(source).with_suffix(".o"))
            object_files.append(obj)
            cmd = [
                gpp,
                "-c",
                "-fPIC",
                source,
                *include_flags,
                "-o",
                obj,
                "-std=c++17",
            ]
            compile_jobs.append((source, cmd))
            logger.debug(f"C++ compile command:\n {' '.join(cmd)}")
            write_to_log(f"C++ compile command: {' '.join(cmd)}")

        def _run_compile(job: tuple[str, list[str]]) -> tuple[str, Any]:
            source, cmd = job
            return source, subprocess.run(
                cmd, check=True, capture_output=True, text=True
            )

        try:
            with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
                compile_results = list(pool.map(_run_compile, compile_jobs))
        except subprocess.CalledProcessError as e:
            so_end = time.time()
            self.program._statistics.cpp_compilation_time += so_end - so_start
            self._handle_compilation_error(e, "C++")
            error_message = f"C++ compilation failed with error:\n{e}\n"
            if e.stderr:
                error_message += f"Details:\n{e.stderr}"
            raise RuntimeError(error_message) from e

        for source, result in compile_results:
            if result.stdout:
                write_to_log(
                    f"C++ compiler output ({source}):\n{result.stdout}"
                )
            if result.stderr:
                write_to_log(
                    f"C++ compiler warnings/errors ({source}):\n{result.stderr}"
                )

        link_cmd = [
            gpp,
            "-shared",
            *object_files,
            "-o",
            str(so_path),
            "-std=c++17",
        ]
        logger.debug(f"C++ link command:\n {' '.join(link_cmd)}")
        write_to_log(f"C++ link command: {' '.join(link_cmd)}")

        try:
            result = subprocess.run(
                link_cmd, check=True, capture_output=True, text=True
            )
            if result.stdout:
                write_to_log(f"C++ linker output:\n{result.stdout}")
            if result.stderr:
                write_to_log(f"C++ linker warnings/errors:\n{result.stderr}")
        except subprocess.CalledProcessError as e:
            so_end = time.time()
            self.program._statistics.cpp_compilation_time += so_end - so_start
            self._handle_compilation_error(e, "C++")
            error_message = f"C++ linking failed with error:\n{e}\n"
            if e.stderr:
                error_message += f"Details:\n{e.stderr}"
            raise RuntimeError(error_message) from e

        so_end = time.time()
        self.program._statistics.cpp_compilation_time += so_end - so_start
        self.program._statistics.compiles += 1
        self.compiled = True

        self._cleanup_old_history()

        logger.debug("Importing wrapper module")
        mist_start = time.time()
        self.wrapper = self.import_wrapper()
        mist_end = time.time()
        self.program._statistics.misc_time += mist_end - mist_start
        write_to_log("Successfully imported wrapper module")

        self._restore_grounded_logical_vars(grounded)
        for name in list(self.program._pending_functions):
            self.program._apply_pending_function(name)

        if restore_state:
            self._restore_saved_state(saved_state)
        self._ensure_activation()

        logger.debug("Compilation process completed successfully")
        write_to_log("Compilation process completed successfully")
        write_to_log(
            f"Total compilation time: {time.time() - time_lap:.2f} seconds"
        )
