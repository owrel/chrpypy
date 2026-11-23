import subprocess
import sys
import time
from pathlib import Path

if __name__ == "__main__":
    examples_dir = Path(__file__).resolve().parent / "examples"

    examples = [
        "colorpalette_factorized.py",
        "colorpalette_simple.py",
        "gcd.py",
        "leq.py",
        "neq.py",
        "parse_program.py",
        "parse_rule.py",
        "piggy_bank.py",
        "prime.py",
        "python_callback.py",
    ]

    start_time = time.perf_counter()

    failed = []
    for name in examples:
        path = examples_dir / name
        print(f"\n--- Running {name} ---")
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(examples_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
        if result.returncode != 0:
            print(f"FAILED: {name} (exit code {result.returncode})")
            failed.append(name)

    elapsed = time.perf_counter() - start_time

    print("\n" + "=" * 40)
    print(f"Ran {len(examples)} examples, {len(failed)} failed")
    print(f"Total time: {elapsed:.2f} seconds")
    if failed:
        print("Failed:", ", ".join(failed))
        sys.exit(1)
