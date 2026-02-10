from pathlib import Path
from typing import TYPE_CHECKING

from .binding_generator import BindingGenerator
from .chr_block_generator import CHRBlockGenerator

if TYPE_CHECKING:
    from ..program import Program


class CHRGenerator:
    def __init__(self, program: "Program"):
        self.program = program
        self.chr_block_generator = CHRBlockGenerator(program)
        self.binding_generator = BindingGenerator(program)

    @staticmethod
    def generate_callback_registry_implementation(
        callback_registry_hh: Path | str,
    ) -> str:
        return f"""
        #include <{callback_registry_hh}>
        void PythonCallbackRegistry::register_function(const std::string& name, py::function func) {{
            callbacks[name] = func;
        }}
        """

    def generate_chrpp(self) -> str:
        code = f"""#include <iostream>
            #include <string>
            #include <chrpp.hh>
            #include <{self.program.helper_hh}>
            """

        code += self.chr_block_generator.generate()
        return code

    def generate_bindings(self) -> str:
        return self.binding_generator.generate()

    def generate_callback_registry_implementation_file(
        self, output_path: Path | str, callback_registry_hh: Path | str
    ) -> str:
        content = self.generate_callback_registry_implementation(
            callback_registry_hh
        )
        Path(output_path).write_text(content)
        return content

    def generate_chrpp_file(self, output_path: Path | str) -> str:
        content = self.generate_chrpp()
        Path(output_path).write_text(content)
        return content

    def generate_bindings_file(self, output_path: Path | str) -> str:
        content = self.generate_bindings()
        Path(output_path).write_text(content)
        return content
