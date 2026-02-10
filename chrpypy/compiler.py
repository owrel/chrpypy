import hashlib
import logging
import operator
import shutil
import subprocess
import sysconfig
import tempfile
import time
from collections.abc import Callable
from importlib import util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pybind11

from .chrgen import CHRGenerator

if TYPE_CHECKING:
    from .constraints import Constraint
    from .program import Program

logger = logging.getLogger(__name__)


class Compiler:
    def __init__(
        self,
        program: "Program",
        max_history: int = 50,
        *,
        use_cache: bool = True,
    ) -> None:
        self.program = program
        self.max_history = max_history
        self.use_cache = use_cache
        self.wrapper = None
        self.chr_gen = CHRGenerator(self.program)
        self.compiled = False

        self.current_hash_folder: Path = (
            Path(tempfile.gettempdir()) / "default _chrpypy_compile"
        )

    def _compute_hash(self) -> str:
        hash_obj = hashlib.sha256()
        hash_obj.update(self.chr_gen.generate_chrpp().encode("utf-8"))
        hash_obj.update(self.chr_gen.generate_bindings().encode("utf-8"))
        return hash_obj.hexdigest()

    def _check_cached_compilation(self) -> tuple[bool, str]:
        current_hash = self._compute_hash()
        hash_folder = self.program.folder / current_hash

        if hash_folder.exists():
            target_so = hash_folder / f"{self.program.name}.so"
            if target_so.exists():
                logger.debug(
                    f"Found cached compilation for hash: {current_hash}"
                )
                return True, current_hash

        return False, current_hash

    def _cleanup_old_history(self) -> None:
        if not self.program.folder.exists():
            return

        hash_dirs = [
            (d, d.stat().st_mtime)
            for d in self.program.folder.iterdir()
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

        target = (
            self.current_hash_folder / f"{self.program.name}.so"
        ).resolve()
        if not target.exists():
            raise ValueError(
                f"FATAL : Could not import target wrapper {target} "
            )

        logger.debug(f"Importing wrapper from {target}")

        spec = util.spec_from_file_location(self.program.name, target)
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

        return getattr(module, self.program.name)()

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
        cmd = [self.program.chrpp_extract_files, str(chrpp_file)]
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

        extracted = [self.current_hash_folder / r for r in res]
        logger.debug(f"Extracted files: {extracted}")
        return extracted

    def _handle_compilation_error(self, error: Exception, stage: str) -> None:
        if self.current_hash_folder and self.current_hash_folder.exists():
            error_folder_name = (
                f"compilation_error_{self.current_hash_folder.name}"
            )
            error_folder = self.program.folder / error_folder_name

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

    def compile(self, *, load_previous_stores: bool = True) -> None:
        save: dict[str, list[Constraint]] = {}
        if (
            load_previous_stores
            and self.compiled
            and self.program.constraint_stores
        ):
            for constraint_store_name in self.program.constraint_stores:
                save[constraint_store_name] = self.program.constraint_stores[
                    constraint_store_name
                ].get()

        logger.debug("Starting compilation process")
        time_lap = time.time()

        logger.debug("Verifying if paths exist...")
        required_paths = {
            "chrpp_path": Path(self.program.chrpp_path),
            "chrppc_path": Path(self.program.chrppc_path),
            "chrpp_runtime": Path(self.program.chrpp_runtime),
            "chrpp_extract_files": Path(self.program.chrpp_extract_files),
            "helper_hh": Path(self.program.helper_hh),
        }

        for name, path in required_paths.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Required path '{name}' does not exist: {path}"
                )
            logger.debug(f"Verified {name}: {path}")

        logger.debug("Setting up build directory")
        if not self.program.folder.exists():
            self.program.folder.mkdir(parents=True)

        cache_exists, current_hash = self._check_cached_compilation()

        if self.use_cache and cache_exists:
            logger.info(
                f"Found cached compilation with matching rules hash: {current_hash}"
            )
            self.current_hash_folder = self.program.folder / current_hash
            self.compiled = True
            mist_start = time.time()
            self.wrapper = self.import_wrapper()
            mist_end = time.time()
            self.program.statistics.misc_time += mist_end - mist_start
            logger.debug("Using cached compilation")
            return

        self.current_hash_folder = self.program.folder / current_hash

        if self.current_hash_folder.exists():
            shutil.rmtree(self.current_hash_folder)
        self.current_hash_folder.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Building in hash folder: {self.current_hash_folder}")

        if not self.current_hash_folder.is_dir():
            raise ValueError("Hash folder must be a directory")
        self.program.statistics.misc_time += time.time() - time_lap

        chrpp_gen_start = time.time()

        logger.info("Generating CHRPP file")
        generated_chrpp_path = (
            self.current_hash_folder / f"{self.program.name}-pychr.chrpp"
        )

        self.chr_gen.generate_chrpp_file(generated_chrpp_path)

        logger.debug(f"Generated CHRPP file at {generated_chrpp_path}")

        chrpp_gen_end = time.time()
        self.program.statistics.generation_time += (
            chrpp_gen_end - chrpp_gen_start
        )

        chrpp_compile_start = time.time()

        logger.info("Compiling CHRPP file")
        cmd = [
            self.program.chrppc_path,
            str(generated_chrpp_path),
            "-o",
            str(self.current_hash_folder),
        ]
        logger.debug(f"CHRPP compiler command:\n {' '.join(cmd)}")
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            chrpp_end = time.time()
            self.program.statistics.chrppc_compilation_time += (
                chrpp_end - chrpp_compile_start
            )
            self._handle_compilation_error(e, "CHRPP")
            raise RuntimeError(
                f"CHRPP compilation failed with error: {e}"
            ) from e

        chrpp_end = time.time()
        self.program.statistics.chrppc_compilation_time += (
            chrpp_end - chrpp_compile_start
        )

        wrapper_start = time.time()

        logger.info("Generating bindings file")

        bindings_path = (
            self.current_hash_folder / f"{self.program.name}_bindings.cpp"
        )
        self.chr_gen.generate_bindings_file(bindings_path)
        logger.debug(f"Generated bindings file at {bindings_path}")

        wrapper_end = time.time()
        self.program.statistics.generation_time += wrapper_end - wrapper_start

        so_start = time.time()

        include_source = [
            str(p) for p in self._extract_files(generated_chrpp_path)
        ]

        if self.program._retrieve_callbacks():
            include_source.append(str(self.program.helper_hh))

        logger.info("Compiling C++ shared library")

        cmd = [
            shutil.which("g++"),
            "-shared",
            "-fPIC",
            *include_source,
            str(bindings_path),
            "-I",
            sysconfig.get_paths()["include"],
            "-I",
            self.program.chrpp_runtime,
            "-I",
            pybind11.get_include(),
            "-o",
            str(self.current_hash_folder / f"{self.program.name}.so"),
            "-std=c++17",
        ]

        logger.debug(f"C++ compiler command:\n {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            so_end = time.time()
            self.program.statistics.cpp_compilation_time += so_end - so_start
            self._handle_compilation_error(e, "C++")
            raise RuntimeError(f"C++ compilation failed with error: {e}") from e

        so_end = time.time()
        self.program.statistics.cpp_compilation_time += so_end - so_start
        self.program.statistics.compiles += 1
        self.compiled = True

        self._cleanup_old_history()

        logger.debug("Importing wrapper module")
        mist_start = time.time()
        self.wrapper = self.import_wrapper()
        mist_end = time.time()
        self.program.statistics.misc_time += mist_end - mist_start
        if load_previous_stores:
            for constraint_store_name, saved_constraints in save.items():
                self.program.constraint_stores[constraint_store_name].posts(
                    saved_constraints
                )

        logger.debug("Compilation process completed successfully")
