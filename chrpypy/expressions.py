from abc import ABC, abstractmethod
from typing import Any, override

from .typesystem import TypeSystem


def ensure_expr(value: Any) -> "Expression":
    if isinstance(value, Expression):
        return value
    if isinstance(value, tuple(TypeSystem.python_types())):
        return Constant(value)
    raise TypeError(f"Cannot convert {type(value)} to Expression")


def introspection(
    expression: "Expression", expression_type: type["Expression"]
) -> list["Expression"]:
    result = []

    if isinstance(expression, expression_type):
        result.append(expression)

    for child in expression.children():
        result.extend(introspection(child, expression_type))

    return result


class Expression(ABC):
    @abstractmethod
    def __repr__(self) -> str:
        pass

    @abstractmethod
    def to_chrpp(self) -> str:
        pass

    def is_grounded(self) -> bool:
        return all(child.is_grounded() for child in self.children())

    def children(self) -> list["Expression"]:  # noqa
        return []

    def node_label(self) -> str:
        return self.__class__.__name__

    def node_symbol(self) -> str | None:  # noqa
        return None

    def __hash__(self) -> int:
        return super().__hash__()

    def __add__(self, other: Any):
        return BinaryOp("+", self, ensure_expr(other))

    def __radd__(self, other: Any):
        return BinaryOp("+", ensure_expr(other), self)

    def __sub__(self, other: Any):
        return BinaryOp("-", self, ensure_expr(other))

    def __rsub__(self, other: Any):
        return BinaryOp("-", ensure_expr(other), self)

    def __mul__(self, other: Any):
        return BinaryOp("*", self, ensure_expr(other))

    def __rmul__(self, other: Any):
        return BinaryOp("*", ensure_expr(other), self)

    def __truediv__(self, other: Any):
        return BinaryOp("/", self, ensure_expr(other))

    def __floordiv__(self, other: Any):
        return BinaryOp("//", self, ensure_expr(other))

    def __mod__(self, other: Any):
        return BinaryOp("%", self, ensure_expr(other))

    def __pow__(self, other: Any):
        return BinaryOp("**", self, ensure_expr(other))

    def __neg__(self):
        return UnaryOp("-", self)

    def __eq__(self, other: object):  # type: ignore
        return Comparison("==", self, ensure_expr(other))

    def __ne__(self, other: object):  # type: ignore
        return Comparison("!=", self, ensure_expr(other))

    def __lt__(self, other: Any):
        return Comparison("<", self, ensure_expr(other))

    def __le__(self, other: Any):
        return Comparison("<=", self, ensure_expr(other))

    def __gt__(self, other: Any):
        return Comparison(">", self, ensure_expr(other))

    def __ge__(self, other: Any):
        return Comparison(">=", self, ensure_expr(other))


class Variable(Expression):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def to_chrpp(self) -> str:
        return self.name.upper() if len(self.name) == 1 else self.name

    def node_label(self) -> str:  # noqa
        return "Variable"

    def node_symbol(self) -> str | None:
        return self.name

    @override
    def is_grounded(self) -> bool:
        return False


class AnonymousVariable(Expression):
    def __init__(self):
        pass

    def __repr__(self):
        return "_"

    def __hash__(self):
        return hash("_")

    def to_chrpp(self) -> str:  # noqa
        return "_"

    def node_label(self) -> str:  # noqa
        return "AnonymousVariable"

    def node_symbol(self) -> str | None:  # noqa
        return "_"

    @override
    def is_grounded(self) -> bool:
        return False


class Constant(Expression):
    def __init__(self, value: Any):
        self.value = value

    def __repr__(self):
        if self.value is None:
            return "None"
        if isinstance(self.value, str):
            return f'"{self.value}"'
        if isinstance(self.value, int):
            return str(self.value)
        return str(self.value)

    def to_chrpp(self) -> str:
        if self.value is None:
            return "null"
        if isinstance(self.value, str):
            return f'"{self.value}"'
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)

    def node_label(self) -> str:  # noqa
        return "Constant"

    def node_symbol(self) -> str | None:
        if self.value is None:
            return "None"
        if isinstance(self.value, str):
            return f'"{self.value}"'
        return str(self.value)

    @override
    def is_grounded(self) -> bool:
        return True


class BinaryOp(Expression):
    OP_MAPPING = {
        "==": "==",
        "!=": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
        "+": "+",
        "-": "-",
        "*": "*",
        "/": "/",
        "//": "/",
        "%": "%",
        "**": "pow",
    }

    def __init__(self, op: str, left: Expression, right: Expression):
        self.op = op
        self.left = left
        self.right = right

    def __repr__(self):
        return f"({self.left} {self.op} {self.right})"

    def to_chrpp(self) -> str:
        left = self.left.to_chrpp()
        right = self.right.to_chrpp()
        if self.op == "**":
            return f"pow({left}, {right})"
        op = self.OP_MAPPING.get(self.op, self.op)
        return f"({left} {op} {right})"

    def children(self) -> list[Expression]:
        return [self.left, self.right]

    def node_label(self) -> str:  # noqa
        return "BinaryOp"

    def node_symbol(self) -> str | None:
        return self.op


class UnaryOp(Expression):
    def __init__(self, op: str, operand: Expression):
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"{self.op}{self.operand}"

    def to_chrpp(self) -> str:
        operand = self.operand.to_chrpp()
        return f"{self.op}{operand}"

    def children(self) -> list[Expression]:
        return [self.operand]

    def node_label(self) -> str:  # noqa
        return "UnaryOp"

    def node_symbol(self) -> str | None:
        return self.op


class FunctionCall(Expression):
    def __init__(self, name: str, *args: Any):
        self.name = name
        self.args = [ensure_expr(arg) for arg in args]

    def __repr__(self):
        args_str = ", ".join(str(arg) for arg in self.args)
        return f"{self.name}({args_str})"

    def to_chrpp(self) -> str:
        args_str = ", ".join(arg.to_chrpp() for arg in self.args)
        return (
            f'registry.call("{self.name}" {"," if args_str else ""} {args_str})'
        )

    def children(self) -> list[Expression]:
        return self.args

    def node_label(self) -> str:  # noqa
        return "FunctionCall"

    def node_symbol(self) -> str | None:
        return self.name


class Success(Expression):
    def __init__(self):
        pass

    def __repr__(self):
        return "success()"

    def to_chrpp(self) -> str:  # noqa
        return "success()"

    def children(self) -> list[Expression]:  # noqa
        return []

    def node_label(self) -> str:  # noqa
        return "success()"

    def node_symbol(self) -> str | None:  # noqa
        return None


class Failure(Expression):
    def __init__(self):
        pass

    def __repr__(self):
        return "fail()"

    def to_chrpp(self) -> str:  # noqa
        return "fail()"

    def children(self) -> list[Expression]:  # noqa
        return []

    def node_label(self) -> str:  # noqa
        return "fail()"

    def node_symbol(self) -> str | None:  # noqa
        return None


class Guard(ABC):
    @abstractmethod
    def to_chrpp(self) -> str:
        pass

    def children(self) -> list["Guard"]:  # noqa
        return []

    def node_label(self) -> str:
        return self.__class__.__name__

    def node_symbol(self) -> str | None:  # noqa
        return None

    def __and__(self, other: "Guard"):
        if isinstance(other, Guard):
            return And(self, other)
        return NotImplemented

    def __or__(self, other: "Guard"):
        if isinstance(other, Guard):
            return Or(self, other)
        return NotImplemented

    def __invert__(self):
        return Not(self)

    def __hash__(self) -> int:
        return super().__hash__()


class Comparison(Guard, Expression):
    OP_MAPPING = {
        "==": "==",
        "!=": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
    }

    def __init__(self, op: str, left: "Expression", right: "Expression"):
        self.op = op
        self.left = left
        self.right = right

    def __repr__(self):
        return f"{self.left} {self.op} {self.right}"

    def to_chrpp(self) -> str:
        left = self.left.to_chrpp()
        right = self.right.to_chrpp()
        if self.op == "==":
            return f"{left} == {right}"
        op = self.OP_MAPPING.get(self.op, self.op)
        return f"{left} {op} {right}"

    def children(self) -> list[Expression]:  # type: ignore[override]
        return [self.left, self.right]

    def node_label(self) -> str:  # noqa
        return "Comparison"

    def node_symbol(self) -> str:
        return self.op


class Unification(Expression):
    def __init__(self, left: "Expression", right: "Expression"):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"{self.left} %= {self.right}"

    def to_chrpp(self) -> str:
        left = self.left.to_chrpp()
        right = self.right.to_chrpp()
        return f"{left} %= {right}"

    def children(self) -> list[Expression]:  # type: ignore[override]
        return [self.left, self.right]

    def node_label(self) -> str:  # noqa
        return "Unification"

    def node_symbol(self) -> str:
        return "%="


class And(Guard):
    def __init__(self, *guards: Guard):
        self.guards = list(guards)

    def __and__(self, other: "Guard"):
        if isinstance(other, Guard):
            return And(*self.guards, other)
        return NotImplemented

    def __repr__(self):
        return f"({' ∧ '.join(str(g) for g in self.guards)})"

    def to_chrpp(self) -> str:
        parts = [g.to_chrpp() for g in self.guards]
        return " and ".join(parts)

    def children(self) -> list[Guard]:
        return self.guards

    def node_label(self) -> str:  # noqa
        return "And"

    def node_symbol(self) -> str | None:  # noqa
        return "∧"


class Or(Guard):
    def __init__(self, *guards: Guard):
        self.guards = list(guards)

    def __or__(self, other: "Guard"):
        if isinstance(other, Guard):
            return Or(*self.guards, other)
        return NotImplemented

    def __repr__(self):
        return f"({' ∨ '.join(str(g) for g in self.guards)})"  # noqa

    def to_chrpp(self) -> str:
        parts = [g.to_chrpp() for g in self.guards]
        return " or ".join(f"({p})" for p in parts)

    def children(self) -> list[Guard]:
        return self.guards

    def node_label(self) -> str:  # noqa
        return "Or"

    def node_symbol(self) -> str | None:  # noqa
        return "∨"  # noqa


class Not(Guard):
    def __init__(self, guard: Guard):
        self.guard = guard

    def __repr__(self):
        return f"¬({self.guard})"

    def to_chrpp(self) -> str:
        inner = self.guard.to_chrpp()
        return f"!({inner})"

    def children(self) -> list[Guard]:
        return [self.guard]

    def node_label(self) -> str:  # noqa
        return "Not"

    def node_symbol(self) -> str | None:  # noqa
        return "¬"


FAILURE = Failure()
SUCCESS = Success()
ANON = AnonymousVariable()
