import pytest
from chrpypy.parser import UnknownConstraintError, parse

from chrpypy import (
    FAILURE,
    SUCCESS,
    Constraint,
    FunctionCall,
    Program,
    PropagationRule,
    SimpagationRule,
)


def _user_rules(program: Program):
    return [
        rule
        for rule in program._rules
        if rule.name is not None and not rule.name.startswith("reset_")
    ]


def test_parse_declarations_and_rule():
    program = Program(name="parser_direct")
    parse(
        """
        <chr_constraint> gcd(int), res(int)
        gcd(N) ==> N > 0 | res(N) ;;
        """,
        program,
    )

    assert program._store_map["gcd"].types == [int]
    assert program._store_map["res"].types == [int]

    (rule,) = _user_rules(program)
    assert isinstance(rule, PropagationRule)
    assert rule.guard is not None
    assert rule.positive_head[0].name == "gcd"
    assert isinstance(rule.body[0], Constraint)
    assert rule.body[0].name == "res"


def test_rules_can_precede_declarations():
    program = Program(name="parser_order")
    parse(
        """
        foo(X) ==> bar(X) ;;
        <chr_constraint> foo(int), bar(int)
        """,
        program,
    )

    (rule,) = _user_rules(program)
    assert isinstance(rule.body[0], Constraint)
    assert rule.body[0].name == "bar"


def test_parse_rule_method():
    program = Program(name="parser_rule")
    program.constraint("foo", [int])
    program.constraint("bar", [int])

    rule = program.parse_rule("r1 @ foo(X) \\ bar(X) <=> X > 0 | foo(X - 1)")

    assert isinstance(rule, SimpagationRule)
    assert rule.name == "r1"
    assert "r1 @ foo(X) \\ bar(X) <=> X > 0 | foo((X - 1));;" in program.chr()


def test_pragmas_are_preserved():
    program = Program(name="parser_pragmas")
    program.constraint("p", [int])

    rule = program.parse_rule("p(X) # passive ==> p(X) # catch_failure ;;")

    assert rule.positive_head[0].pragma == "passive"
    body_item = rule.body[0]
    assert isinstance(body_item, Constraint)
    assert body_item.pragma == "catch_failure"


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("true", SUCCESS),
        ("success", SUCCESS),
        ("false", FAILURE),
        ("failure", FAILURE),
    ],
)
def test_body_literals(literal: str, expected: object):
    program = Program(name=f"parser_literal_{literal}")
    program.constraint("foo", [int])

    rule = program.parse_rule(f"foo(X) ==> {literal}")

    assert rule.body[0] is expected


def test_body_literal_mixed_with_constraint():
    program = Program(name="parser_literal_mixed")
    program.constraint("foo", [int])
    program.constraint("bar", [int])

    rule = program.parse_rule("foo(X) ==> bar(X), true")

    assert isinstance(rule.body[0], Constraint)
    assert rule.body[1] is SUCCESS


def test_undeclared_body_call_becomes_callback():
    program = Program(name="parser_callback")
    program.constraint("foo", [int])

    rule = program.parse_rule("foo(X) ==> print(X)")

    assert isinstance(rule.body[0], FunctionCall)


def test_unknown_head_constraint_raises():
    program = Program(name="parser_unknown")

    with pytest.raises(UnknownConstraintError):
        program.parse_rule("foo(X) ==> foo(X)")


def test_parse_rule_rejects_declarations():
    program = Program(name="parser_decl_in_rule")

    with pytest.raises(ValueError):
        program.parse_rule("<chr_constraint> foo(int)")
