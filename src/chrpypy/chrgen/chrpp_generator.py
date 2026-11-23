from typing import TYPE_CHECKING

from ..rules import Rule
from ..typesystem import TypeSystem

if TYPE_CHECKING:
    from ..program import Program


class CHRPPGenerator:
    def __init__(self, program: "Program"):
        self.program = program

    def _get_constraint_signatures(
        self, *, include_builtins: bool = True
    ) -> list[str]:
        signatures = set()
        for cs in sorted(
            self.program._store_map.values(), key=lambda x: x.name
        ):
            if not include_builtins and cs.name.startswith(
                self.program._BUILTIN_PREFIX
            ):
                continue
            if not cs.initialized:
                raise RuntimeError(
                    f"The constraint store {cs.name} is not initialized. Please provided concrete type description or make sure that type can be DIRECLTY infered from the args passed in the constraint"
                )

            signature = f"{cs.name}({', '.join([TypeSystem.python_to_chr(python_t) for python_t in cs.types])})"
            signatures.add(signature)
        return sorted(signatures)

    def generate(
        self,
        rules: list[Rule] | None = None,
        *,
        include_builtins: bool = True,
    ) -> str:
        signatures = self._get_constraint_signatures(
            include_builtins=include_builtins
        )

        chr_block = "/**\n"
        if self.program._retrieve_callbacks():
            chr_block += f'\t<CHR name="{self.program.name}" parameters="PythonCallbackRegistry& registry">\n'
        else:
            chr_block += f'\t<CHR name="{self.program.name}">\n'

        chr_block += f"\t<chr_constraint> {', '.join(signatures)}\n"

        if rules is None:
            rules = self.program._rules

        for rule in rules:
            chr_block += "\t\t" + rule.to_chrpp()

        chr_block += "\t</CHR>\n"
        chr_block += "*/"

        return chr_block
