from pathlib import Path

import pytest

from chrpypy import (
    BinaryOp,
    Constant,
    Constraint,
    Program,
    Symbol,
    Unification,
)


@pytest.fixture
def program(tmp_path: Path) -> Program:
    program = Program(
        name="parser_unification",
        folder=tmp_path,
        compile_on="compile",
    )
    program.constraint("foo", [int])
    program.constraint("bar", [int])
    return program


def test_parse_unification_with_constant(program: Program) -> None:
    rule = program.parse_rule("foo(X) <=> X %= 3")

    (body,) = rule.body
    assert isinstance(body, Unification)
    assert isinstance(body.left, Symbol)
    assert isinstance(body.right, Constant)
    assert body.left.name == "X"
    assert body.right.value == 3


def test_parse_unification_with_symbol(program: Program) -> None:
    program.constraint("baz", [int])

    rule = program.parse_rule("foo(X), bar(Y) <=> X %= Y, baz(X)")

    unify, other = rule.body
    assert isinstance(unify, Unification)
    assert isinstance(unify.left, Symbol)
    assert isinstance(unify.right, Symbol)
    assert unify.left.name == "X"
    assert unify.right.name == "Y"
    assert isinstance(other, Constraint)
    assert other.name == "baz"


def test_modulo_still_parses_as_binary_op(program: Program) -> None:
    rule = program.parse_rule("foo(X) <=> bar(X % 2)")

    (body,) = rule.body
    assert isinstance(body, Constraint)
    arg = body.args[0]
    assert isinstance(arg, BinaryOp)
    assert arg.op == "%"


def test_unification_renders_as_chr(program: Program) -> None:
    program.parse_rule("foo(X), bar(Y) <=> X %= Y")

    assert "X %= Y" in program.chr()
