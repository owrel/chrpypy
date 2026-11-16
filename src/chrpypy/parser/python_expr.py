from __future__ import annotations

import ast
from typing import NoReturn

from chrpypy.expressions import (
    ANON,
    And,
    BinaryOp,
    Comparison,
    Constant,
    Expression,
    Ground,
    Guard,
    Not,
    Or,
    Symbol,
    TermCall,
    UnaryOp,
)

_BIN_OPS: dict[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
}

_UNARY_OPS: dict[type[ast.unaryop], str] = {
    ast.USub: "-",
    ast.UAdd: "+",
}

_CMP_OPS: dict[type[ast.cmpop], str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}


class UnsupportedExpressionError(ValueError):
    def __init__(self, source: str, reason: str | None = None):
        message = f"Unsupported CHR expression: {source!r}"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
        self.source = source


class _ExpressionTranslator(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source

    def _unsupported(
        self, node: ast.AST, reason: str | None = None
    ) -> NoReturn:
        raise UnsupportedExpressionError(ast.unparse(node), reason)

    def translate(self, node: ast.AST):
        return self.visit(node)

    def generic_visit(self, node: ast.AST) -> NoReturn:
        self._unsupported(node, f"{type(node).__name__} is not supported")

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        return Constant(node.value)

    def visit_Name(self, node: ast.Name):
        if node.id == "_":
            return ANON
        return Symbol(node.id)

    def visit_BinOp(self, node: ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            self._unsupported(node, "operator is not supported")
        return BinaryOp(op, self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return Not(self._as_guard(node.operand))
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            self._unsupported(node, "unary operator is not supported")
        return UnaryOp(op, self.visit(node.operand))

    def visit_BoolOp(self, node: ast.BoolOp):
        guards = [self._as_guard(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return And(*guards)
        return Or(*guards)

    def visit_Compare(self, node: ast.Compare):
        if len(node.ops) != 1:
            self._unsupported(node, "chained comparisons are not supported")
        op = _CMP_OPS.get(type(node.ops[0]))
        if op is None:
            self._unsupported(node, "comparison operator is not supported")
        return Comparison(
            op, self.visit(node.left), self.visit(node.comparators[0])
        )

    def visit_Attribute(self, node: ast.Attribute) -> NoReturn:
        self._unsupported(node, "only X.ground() is supported")

    def visit_Call(self, node: ast.Call) -> Expression | Guard:
        if node.keywords:
            self._unsupported(node, "keyword arguments are not supported")

        if isinstance(node.func, ast.Name):
            if node.func.id == "ground" and len(node.args) == 1:
                return Ground(self._as_symbol(node.args[0]))
            return TermCall(
                node.func.id, *(self.visit(arg) for arg in node.args)
            )

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "ground"
            and not node.args
        ):
            return Ground(self._as_symbol(node.func.value))

        return self._unsupported(
            node, "only plain function calls are supported"
        )

    def _as_guard(self, node: ast.AST) -> Guard:
        result = self.visit(node)
        if not isinstance(result, Guard):
            raise UnsupportedExpressionError(
                ast.unparse(node), "expected a boolean guard"
            )
        return result

    def _as_symbol(self, node: ast.AST) -> Symbol:
        result = self.visit(node)
        if not isinstance(result, Symbol):
            raise UnsupportedExpressionError(
                ast.unparse(node), "expected a variable"
            )
        return result


def _parse(source: str) -> ast.Expression:
    try:
        return ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise UnsupportedExpressionError(
            source, f"invalid Python expression: {exc.msg}"
        ) from exc


def translate_expression(source: str) -> Expression:
    result = _ExpressionTranslator(source).translate(_parse(source))
    if not isinstance(result, Expression):
        raise UnsupportedExpressionError(source, "expected a value expression")
    return result


def translate_guard(source: str) -> Guard:
    result = _ExpressionTranslator(source).translate(_parse(source))
    if not isinstance(result, Guard):
        raise UnsupportedExpressionError(source, "expected a boolean guard")
    return result
