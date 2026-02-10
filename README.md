# CHR 🥧🥧

A Python CHR implementation using [chrpp](https://vynce.gitlab.io/chrpp/) as backend

# Installation Requirements

## System Dependencies (Linux):

- g++ (gcc-c++)
- cmake
- make
- git

## Installation:

```bash
git clone https://github.com/owrel/chrpypy.git
cd chrpypy
pip install . -v
```

If wou already have an installation of chrpp (compatible with chrpypy), you can set the following env variable BEFORE installing chrpypy with pip :

```bash
export CHRPP_PATH="path/to/chrpp"
```

## Error during installation

If you encounter a compilation error during installation (for example, due to missing build tools like g++, cmake, or make), you can force a fresh build by ignoring the cached chrpp compilation. Use the following command. Note: This command will not resolve the underlying compilation error; it simply ensures a new build attempt.

```bash
CHRPP_IGNORE_CACHE=1 pip install . -v
```
