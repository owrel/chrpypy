# CHR 🥧🥧

A Python CHR implementation using [chrpp](https://vynce.gitlab.io/chrpp/) as backend

# Installation Requirements

## System Dependencies (Linux):

- g++ (gcc-c++)
- cmake (>=3.16)
- make
- git (for submodule)

## Installation:

```bash
git clone https://github.com/owrel/chrpypy.git
cd chrpypy
pip install . -v
```

If wou already have an installation of chrpp (compatible with chrpypy), you can set the following env variable BEFORE installing chrpypy with pip :

```bash
export CHRPP_PATH="path/to/chrpp
```
