from collections.abc import Callable
from pathlib import Path
from typing import Any

from graphviz import Source
from IPython.display import Image

from .constraints import Constraint
from .expressions import (
    Expression,
    Failure,
    FunctionCall,
    Guard,
    Success,
    Unification,
)
from .program import Program
from .rules import (
    BodyType,
    PropagationRule,
    Rule,
    SimpagationRule,
    SimplificationRule,
)


class Renderer:
    def __init__(self, dot_content: str):
        self._dot_content = dot_content
        self._source = Source(dot_content, format="png")

    def get_dot_string(self) -> str:
        return self._dot_content

    def save_dot(self, filename: str) -> None:
        Path.write_text(Path(filename), self._dot_content)

    def save_png(self, filename: str) -> None:
        png_data = self._source.pipe()
        Path(filename).write_bytes(png_data)

    def render_png(self) -> bytes:
        return self._source.pipe()

    def render_png_repl(self) -> Image:  # type: ignore
        return Image(self._source.pipe())


class _Parser:
    @staticmethod
    def _create_graph_header() -> list[str]:
        return [
            "digraph AST {",
            "    graph [rankdir=TB, nodesep=0.3, ranksep=0.4];",
            "    node [shape=box, style=rounded, fontsize=12];",
            "    edge [arrowhead=none];",
            "",
        ]

    @staticmethod
    def _finalize_graph(nodes: list[str], edges: list[str]) -> str:
        dot_content = _Parser._create_graph_header()
        dot_content.extend(nodes)
        if edges:
            dot_content.append("")
            dot_content.extend(edges)
        dot_content.append("}")
        return "\n".join(dot_content)

    @staticmethod
    def _create_node_adder(
        nodes: list[str], edges: list[str], counter: list[int]
    ) -> Callable:
        def add_node(
            content: str, parent_id: str | None = None, shape: str = "box"
        ) -> str:
            node_id = f"node{counter[0]}"
            counter[0] += 1

            nodes.append(f'    {node_id} [label="{content}", shape={shape}];')

            if parent_id:
                edges.append(f"    {parent_id} -> {node_id};")

            return node_id

        return add_node

    @staticmethod
    def _add_tree_generic(
        obj: Any,
        parent_id: str | None,
        add_node: Callable,
    ) -> str:
        if hasattr(obj, "node_label"):
            label = obj.node_label()
        else:
            label = obj.__class__.__name__

        if hasattr(obj, "node_symbol") and obj.node_symbol():
            symbol = obj.node_symbol()
            symbol = symbol.replace("\\", "\\\\")
            node_content = f"{label}\\n{symbol}"
        else:
            node_content = label

        node_id = add_node(node_content, parent_id)

        if hasattr(obj, "children"):
            children = obj.children()
            for child in children:
                if child is not None:
                    _Parser._add_tree_generic(child, node_id, add_node)

        return node_id

    @staticmethod
    def _add_expression_tree(
        expr: "Expression", parent_id: str | None, add_node: Callable
    ) -> str:
        return _Parser._add_tree_generic(expr, parent_id, add_node)

    @staticmethod
    def _add_guard_tree(
        guard: "Guard", parent_id: str, add_node: Callable
    ) -> str:
        guard_root_id = add_node("Guard", parent_id, "diamond")
        _Parser._add_tree_generic(guard, guard_root_id, add_node)
        return guard_root_id

    @staticmethod
    def _add_constraint_node(
        constraint: "Constraint | Success | Failure | FunctionCall | Unification",
        parent_id: str,
        add_node: Callable,
    ) -> str:
        if isinstance(constraint, Constraint):
            constraint_id = add_node(
                f"Constraint\\n{constraint.name}", parent_id
            )

            for arg in constraint.args:
                if isinstance(arg, Expression):
                    _Parser._add_expression_tree(arg, constraint_id, add_node)
                else:
                    add_node(str(arg), constraint_id)

            return constraint_id

        return add_node(f"{constraint}", parent_id)

    @staticmethod
    def _add_constraint_list(
        constraints: list["Constraint"],
        parent_id: str,
        label: str,
        add_node: Callable,
    ) -> None:
        if not constraints:
            return

        list_id = add_node(label, parent_id, "ellipse")
        for constraint in constraints:
            _Parser._add_constraint_node(constraint, list_id, add_node)

    @staticmethod
    def _add_body_content(
        body: BodyType,
        parent_id: str,
        add_node: Callable,
    ) -> None:
        body_list_id = add_node("Body", parent_id, "ellipse")
        if body is None:
            add_node("true", body_list_id)
        elif isinstance(body, list):
            for constraint in body:
                _Parser._add_constraint_node(constraint, body_list_id, add_node)
        else:
            _Parser._add_constraint_node(
                constraint=body, parent_id=body_list_id, add_node=add_node
            )

    @staticmethod
    def parse_expression(expr: "Expression") -> Renderer:
        nodes = []
        edges = []
        counter = [0]
        add_node = _Parser._create_node_adder(nodes, edges, counter)

        _Parser._add_expression_tree(expr, None, add_node)

        dot_content = _Parser._finalize_graph(nodes, edges)
        return Renderer(dot_content)

    @staticmethod
    def parse_guard(guard: "Guard") -> Renderer:
        nodes = []
        edges = []
        counter = [0]
        add_node = _Parser._create_node_adder(nodes, edges, counter)

        _Parser._add_tree_generic(guard, None, add_node)

        dot_content = _Parser._finalize_graph(nodes, edges)
        return Renderer(dot_content)

    @staticmethod
    def parse_rule(rule: "Rule") -> Renderer:
        return _Parser.parse_rules([rule])

    @staticmethod
    def parse_rules(rules: "list[Rule]") -> Renderer:
        return _Parser.parse_rules_and_constraints(rules, [])

    @staticmethod
    def parse_constraints(constraints: "list[Constraint]") -> Renderer:
        return _Parser.parse_rules_and_constraints([], constraints)

    @staticmethod
    def parse_rules_and_constraints(
        rules: "list[Rule]", constraints: "list[Constraint]"
    ) -> Renderer:
        nodes = []
        edges = []
        counter = [0]
        add_node = _Parser._create_node_adder(nodes, edges, counter)

        main_container_id = add_node("CHR Program", shape="plaintext")

        if rules:
            rules_container_id = add_node(
                "Rules", parent_id=main_container_id, shape="plaintext"
            )
            for rule in rules:
                root_id = add_node(
                    rule.to_str().replace("\\", "\\\\"),
                    parent_id=rules_container_id,
                    shape="doubleoctagon",
                )

                if rule.positive_head:
                    _Parser._add_constraint_list(
                        rule.positive_head, root_id, "+h", add_node
                    )
                if rule.negative_head:
                    _Parser._add_constraint_list(
                        rule.negative_head, root_id, "-h", add_node
                    )

                if hasattr(rule, "guard") and rule.guard:
                    _Parser._add_guard_tree(rule.guard, root_id, add_node)

                if hasattr(rule, "body"):
                    _Parser._add_body_content(rule.body, root_id, add_node)

        if constraints:
            constraints_container_id = add_node(
                "Constraints", parent_id=main_container_id, shape="plaintext"
            )
            for constraint in constraints:
                _Parser._add_constraint_node(
                    constraint, constraints_container_id, add_node
                )

        dot_content = _Parser._finalize_graph(nodes, edges)
        return Renderer(dot_content)

    @staticmethod
    def parse_program(program: "Program") -> Renderer:
        return _Parser.parse_rules_and_constraints(program.rules, [])


def viz(
    obj: Expression | Guard | Constraint | Rule | list | Program,
) -> Renderer:
    if isinstance(obj, Program):
        return _Parser.parse_program(obj)

    if isinstance(obj, (SimplificationRule, PropagationRule, SimpagationRule)):
        return _Parser.parse_rule(obj)

    if isinstance(obj, Rule):
        return _Parser.parse_rules([obj])

    if isinstance(obj, Constraint):
        return _Parser.parse_constraints([obj])

    if isinstance(obj, Guard):
        return _Parser.parse_guard(obj)

    if isinstance(obj, Expression):
        return _Parser.parse_expression(obj)

    if isinstance(obj, list) and obj:
        if isinstance(obj[0], Rule):
            return _Parser.parse_rules(obj)
        if isinstance(obj[0], Constraint):
            return _Parser.parse_constraints(obj)

    raise TypeError(
        f"Unsupported object type for parsing: {type(obj).__name__}. "
        f"Supported types: Expression, Guard, Constraint, Rule, Program, "
        f"or lists of Rules/Constraints."
    )
