from typing import TYPE_CHECKING

from ..rules import Rule
from ..typesystem import TypeSystem
from .constraint_formatter import ConstraintFormatter

if TYPE_CHECKING:
    from ..program import Program


class CHRBlockGenerator:
    def __init__(self, program: "Program"):
        self.program = program

    def _get_constraint_signatures(self) -> list[str]:
        signatures = set()
        for cs in self.program.constraint_stores.values():
            signature = f"{cs.name}({', '.join([TypeSystem.python_to_chr(python_t) for python_t in cs.types])})"
            signatures.add(signature)
        return list(signatures)

    def _generate_rule_string(self, rule: Rule) -> str:
        rule_str = "\t\t"

        if rule.name:
            rule_str += f"{rule.name} @ "
        else:
            rule_str += f"rule{rule._id} @ "

        if rule.negative_head and rule.positive_head:
            positive = ConstraintFormatter.format_head(rule.positive_head)
            negative = ConstraintFormatter.format_head(rule.negative_head)
            rule_str += f"{positive} \\ {negative} <=> "
        elif rule.negative_head and not rule.positive_head:
            rule_str += (
                f"{ConstraintFormatter.format_head(rule.negative_head)} <=> "
            )
        elif rule.positive_head:
            rule_str += (
                f"{ConstraintFormatter.format_head(rule.positive_head)} ==> "
            )

        if rule.guard:
            guard_str = rule.guard.to_chrpp()
            rule_str += f"{guard_str} | "

        rule_str += ConstraintFormatter.format_body(rule.body)
        rule_str += ";;\n"

        return rule_str

    def generate(self) -> str:
        signatures = self._get_constraint_signatures()

        chr_block = "/**\n"
        if self.program._retrieve_callbacks():
            chr_block += f'\t<CHR name="{self.program.name}" parameters="PythonCallbackRegistry& registry">\n'
        else:
            chr_block += f'\t<CHR name="{self.program.name}">\n'

        chr_block += f"\t<chr_constraint> {', '.join(signatures)}\n"

        for rule in self.program.rules:
            chr_block += self._generate_rule_string(rule)

        chr_block += "\t</CHR>\n"
        chr_block += "*/"

        return chr_block
