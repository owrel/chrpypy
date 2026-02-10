# noqa
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.install import install

CHRPP_REPO = "https://gitlab.com/vynce/chrpp"
CHRPP_COMMIT = "d26d6c17cb35d04526014bc21468a4"
IGNORE_CACHE = bool(int(os.getenv("CHRPP_IGNORE_CACHE", "0")))


class CustomInstall(install):
    def run(self) -> None:
        if not self.install_lib:
            sys.exit(1)

        install_path = Path(self.install_lib) / "chrpypy"
        cache_path = Path(tempfile.gettempdir()) / "chrpp_cache"
        build_path = cache_path

        chrpp_path = os.getenv("CHRPP_PATH")

        if chrpp_path:
            print(
                "CHRPP already installed (environment variable detected). Skipping compilation."
            )
            super().run()
            return

        if (install_path / "chrpp").exists():
            shutil.rmtree(install_path / "chrpp")
        install_path.mkdir(parents=True, exist_ok=True)

        print("Warning : CHRPP will be installed ONLY for chrpypy")
        try:
            if IGNORE_CACHE and cache_path.exists():
                shutil.rmtree(cache_path)

            if not IGNORE_CACHE and cache_path.exists():
                print("Using cached CHRPP from /tmp...")
                shutil.copytree(cache_path, install_path / "chrpp")
                print("CHRPP copied from cache successfully")

            else:
                print("Start cloning...")
                cache_path.parent.mkdir(parents=True, exist_ok=True)

                git = shutil.which("git")
                if not git:
                    raise RuntimeError("Did not find dependency: git")

                subprocess.run(
                    [git, "clone", CHRPP_REPO, str(cache_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                subprocess.run(
                    [git, "-C", str(cache_path), "checkout", CHRPP_COMMIT],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                print("CHRPP cloned successfully")
                print("Compiling CHRPP...")

                cmake = shutil.which("cmake")
                if not cmake:
                    raise RuntimeError("Did not find dependency: cmake")

                build_path.mkdir(parents=True, exist_ok=True)

                # Configure (out-of-source)
                subprocess.run(
                    [
                        cmake,
                        "-S",
                        str(cache_path),
                        "-B",
                        str(build_path),
                        "-DEXAMPLES=OFF",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                make = shutil.which("make")
                if not make:
                    raise RuntimeError("Did not find dependency: make")
                subprocess.run(
                    [make, "-C", str(build_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                print("Done compiling.")

                shutil.copytree(cache_path, install_path / "chrpp")
                print("CHRPP cached for future use")

            src_dir = Path("misc").resolve()
            dest_dir = install_path / "chrpp" / "misc"
            dest_dir.mkdir(parents=True, exist_ok=True)

            if src_dir.exists() and src_dir.is_dir():
                for item in src_dir.iterdir():
                    if item.is_file():
                        shutil.copy(item, dest_dir / item.name)
                        print(f"Copied {item.name} to chrpp/misc")
                print("All misc files copied successfully.")
            else:
                raise FileNotFoundError(
                    f"Did not find misc directory: {src_dir}"
                )

            print("Done.")
        except Exception as e:
            print(e)
            raise e from e

        super().run()


setup(
    packages=find_packages(),
    cmdclass={"install": CustomInstall},
)
