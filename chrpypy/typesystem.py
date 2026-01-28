from collections.abc import Callable
from typing import Any


def int_caster(input: str) -> int:
    try:
        return int(input)
    except Exception:
        raise ValueError(
            f"Could not cast {input} of type {type(input)} to int"
        ) from None


def float_caster(input: str) -> float:
    try:
        return float(input)
    except Exception:
        raise ValueError(
            f"Could not cast {input} of type {type(input)} to float"
        ) from None


def str_caster(input: str) -> str:
    try:
        return str(input)
    except Exception:
        raise ValueError(
            f"Could not cast {input} of type {type(input)} to str"
        ) from None


def bool_caster(input: str) -> bool:
    input = input.strip()
    if input.lower() == "false":
        return False
    if input.lower() == "true":
        return True
    if input == "1":
        return True
    if input == "0":
        return False
    raise ValueError(
        f"Could not cast  {input} of type {type(input)} to bool"
    ) from None


class TypeSystem:
    # Type : (chr, cpp)
    _mapping: dict[type, tuple[str, str]] = {
        int: ("?int", "int"),
        float: ("?double", "double"),
        str: ("std::string", "std::string"),
        bool: ("?bool", "bool"),
    }

    _casters: dict[type, Callable[[str], Any]] = {
        int: int_caster,
        float: float_caster,
        str: str_caster,
        bool: bool_caster,
    }

    @staticmethod
    def cpp_to_python(cpp_type: str) -> type:
        for python_type, tpl in TypeSystem._mapping.items():
            if tpl[0] == cpp_type:
                return python_type
        raise ValueError(f"Did not find a match for the cpp type : {cpp_type}")

    @staticmethod
    def chr_to_python(chr_type: str) -> type:
        for python_type, tpl in TypeSystem._mapping.items():
            if tpl[1] == chr_type:
                return python_type
        raise ValueError(f"Did not find a match for the cpp type : {chr_type}")

    @staticmethod
    def python_to_chr(python_type: type) -> str:
        pt = TypeSystem._mapping.get(python_type)
        if pt:
            return pt[0]
        raise ValueError(
            f"Did not find a CHR match for python type {python_type}"
        )

    @staticmethod
    def python_to_cpp(python_type: type) -> str:
        tpl = TypeSystem._mapping.get(python_type)
        if tpl:
            return tpl[1]
        raise ValueError(
            f"Did not find a CPP match for python type {python_type}"
        )

    @staticmethod
    def python_types() -> list[type]:
        return list(TypeSystem._mapping.keys())

    @staticmethod
    def register_custom_caster(
        python_type: type, caster_func: Callable
    ) -> None:
        TypeSystem._casters[python_type] = caster_func

    @staticmethod
    def register_custom_type(t: type, chr_type: str, cpp_type: str) -> None:
        TypeSystem._mapping[t] = (chr_type, cpp_type)

    @staticmethod
    def cast(value: str, python_type: type) -> Any:
        if python_type in TypeSystem._casters:
            return TypeSystem._casters[python_type](value)

        raise ValueError(f"Cannot cast to unsupported type: {python_type}")
