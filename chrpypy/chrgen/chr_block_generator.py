from typing import TYPE_CHECKING

from ..typesystem import TypeSystem

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
        return sorted(signatures)

    def generate(self) -> str:
        signatures = self._get_constraint_signatures()

        chr_block = "/**\n"
        if self.program._retrieve_callbacks():
            chr_block += f'\t<CHR name="{self.program.name}" parameters="PythonCallbackRegistry& registry">\n'
        else:
            chr_block += f'\t<CHR name="{self.program.name}">\n'

        chr_block += f"\t<chr_constraint> {', '.join(signatures)}\n"

        for rule in self.program.rules:
            chr_block += rule._generate_chr_rule_string()

        chr_block += "\t</CHR>\n"
        chr_block += "*/"

        return chr_block
