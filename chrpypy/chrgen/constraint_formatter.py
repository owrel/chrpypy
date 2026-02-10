from ..constraints import Constraint
from ..expressions import Failure, FunctionCall, Success, Unification
from ..rules import BodyType, HeadType


class ConstraintFormatter:
    @staticmethod
    def format_constraint(constraint: Constraint) -> str:
        if not constraint.args:
            return f"{constraint.name}()"

        args_str = ", ".join(arg.to_chrpp() for arg in constraint.args)
        if constraint.pragma:
            return f"{constraint.name}({args_str})#{constraint.pragma}"
        return f"{constraint.name}({args_str})"

    @staticmethod
    def format_head(head: HeadType) -> str:
        if head is None:
            return ""

        if isinstance(head, list):
            if not head:
                return ""
            return ", ".join(
                ConstraintFormatter.format_constraint(c) for c in head
            )

        if isinstance(head, Constraint):
            return ConstraintFormatter.format_constraint(head)

        return ""

    @staticmethod
    def format_body(body: BodyType) -> str:
        if len(body) == 0:
            return "success()"

        if isinstance(body, (Success, Failure)):
            return body.to_chrpp()

        if isinstance(body, FunctionCall):
            return body.to_chrpp()

        if isinstance(body, list):
            if not body:
                return "success()"

            formatted_parts = []
            for item in body:
                if isinstance(item, Constraint):
                    formatted_parts.append(
                        ConstraintFormatter.format_constraint(item)
                    )
                elif isinstance(
                    item, (Success, Failure, FunctionCall, Unification)
                ):
                    formatted_parts.append(item.to_chrpp())

            return ", ".join(formatted_parts)

        if isinstance(body, Constraint):
            return ConstraintFormatter.format_constraint(body)

        return "success()"
