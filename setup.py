import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution

CHRPP_REPO = "https://gitlab.com/vynce/chrpp"
CHRPP_COMMIT = "eb411d7abac4a9d4fe2a84a9de29cb48123aa040"
IGNORE_CACHE = bool(int(os.getenv("CHRPP_IGNORE_CACHE", "0")))

CHRPP_CACHE = Path(tempfile.gettempdir()) / "chrpp_cache"


_CHRPP_ARTIFACTS = [
    "chrppc/chrppc",
    "runtime",
    "misc/chrpp_extract_files",
]


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"Did not find required dependency: {tool}")
    return path


def _build_chrpp() -> Path | None:
    """Return the directory holding a compiled chrpp tree, or ``None`` when
    ``CHRPP_PATH`` is set (external chrpp, nothing to bundle).
    """
    if os.getenv("CHRPP_PATH"):
        print("CHRPP_PATH is set; using external chrpp (not bundled).")
        return None

    cache_path = CHRPP_CACHE
    built = (cache_path / "chrppc" / "chrppc").exists()

    if IGNORE_CACHE or not built:
        if cache_path.exists():
            shutil.rmtree(cache_path)

        print("Cloning CHRPP...")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [_require("git"), "clone", CHRPP_REPO, str(cache_path)], check=True
        )
        subprocess.run(
            [_require("git"), "-C", str(cache_path), "checkout", CHRPP_COMMIT],
            check=True,
        )

        print("Compiling CHRPP...")
        subprocess.run(
            [
                _require("cmake"),
                "-S",
                str(cache_path),
                "-B",
                str(cache_path),
                "-DEXAMPLES=OFF",
            ],
            check=True,
        )
        subprocess.run([_require("make"), "-C", str(cache_path)], check=True)
        print("CHRPP built successfully.")
    else:
        print(f"Using cached CHRPP from {cache_path}")

    return cache_path


class BuildPy(build_py):
    """Build the Python package and bundle the compiled chrpp engine."""

    def run(self) -> None:
        chrpp_src = _build_chrpp()

        super().run()

        if chrpp_src is None:
            return

        if getattr(self, "editable_mode", False):
            dest = Path(self.get_package_dir("chrpypy")) / "chrpp"
        else:
            dest = Path(self.build_lib) / "chrpypy" / "chrpp"

        if dest.exists():
            shutil.rmtree(dest)

        for rel in _CHRPP_ARTIFACTS:
            src = chrpp_src / rel
            if not src.exists():
                raise FileNotFoundError(f"Missing chrpp artifact: {src}")

            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        print(f"Bundled chrpp engine into {dest}")


class BinaryDistribution(Distribution):
    """Mark the wheel as platform-specific because it bundles native binaries."""

    def has_ext_modules(self) -> bool:
        return True


setup(
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"chrpypy": ["misc/*.hh"]},
    cmdclass={"build_py": BuildPy},
    distclass=BinaryDistribution,
)
