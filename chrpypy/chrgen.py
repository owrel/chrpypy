from pathlib import Path
from typing import TYPE_CHECKING

from .constraints import Constraint, ConstraintStore
from .expressions import (
    Failure,
    FunctionCall,
    Success,
)
from .rules import BodyType, HeadType, Rule
from .typesystem import TypeSystem

if TYPE_CHECKING:
    from .program import Program


class CHRGenerator:
    def __init__(
        self,
        program: "Program",
    ):
        self.program = program

    @staticmethod
    def _format_constraint(constraint: Constraint) -> str:
        if not constraint.args:
            return f"{constraint.name}()"
        args_str = ", ".join(arg.to_chrpp() for arg in constraint.args)
        return f"{constraint.name}({args_str})"

    @staticmethod
    def _format_head(head: HeadType) -> str:
        if head is None:
            return ""
        if isinstance(head, list):
            if not head:
                return ""
            return ", ".join(CHRGenerator._format_constraint(c) for c in head)
        if isinstance(head, Constraint):
            return CHRGenerator._format_constraint(head)
        return ""

    @staticmethod
    def _format_body(body: BodyType) -> str:
        if body is None:
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
                        CHRGenerator._format_constraint(item)
                    )
                elif isinstance(item, (Success, Failure, FunctionCall)):
                    formatted_parts.append(item.to_chrpp())
            return ", ".join(formatted_parts)
        if isinstance(body, Constraint):
            return CHRGenerator._format_constraint(body)
        return "success()"

    @staticmethod
    def _constraint_store_chr_signature(cs: ConstraintStore) -> str:
        return f"{cs.name}({', '.join([TypeSystem.python_to_chr(python_t) for python_t in cs.types])})"

    @staticmethod
    def _constraint_store_add_function(cs: ConstraintStore) -> str:
        if len(cs.types) < 0:
            signature = f"void add_{cs.name}()"
        else:
            args = ", ".join(
                [
                    f"{TypeSystem.python_to_cpp(python_t)} arg{idx}"
                    for idx, python_t in enumerate(cs.types)
                ]
            )
            signature = f"void add_{cs.name}({args})"

        body = f"{{ space->{cs.name}({', '.join(f'chr::Logical_var_ground<{TypeSystem.python_to_cpp(python_t)}>(arg{idx})' for idx, python_t in enumerate(cs.types))}); }}"

        return f"{signature} {{ \n{body} }}"

    @staticmethod
    def _constraint_store_wrapper_definition(
        cs: ConstraintStore, program: "Program"
    ) -> str:
        if len(cs.types) > 0:
            return f'.def("add_{cs.name}", &{program.name}Wrapper::add_{cs.name}, "Add {cs.name} constraint", {", ".join(f'py::arg("arg{i}")' for i in range(len(cs.types)))})'

        return f'.def("add_{cs.name}", &{program.name}Wrapper::add_{cs.name}, "Add {cs.name} constraint")'

    def _generate_chr_block(self) -> str:
        signatures = list(
            {
                self._constraint_store_chr_signature(cs)
                for _, cs in self.program.constraint_stores.items()
            }
        )

        chr_block = "/**\n"
        if self.program._is_using_py_callback():  # noqa
            chr_block += f'\t<CHR name="{self.program.name}" parameters="PythonCallbackRegistry& registry">\n'
        else:
            chr_block += f'\t<CHR name="{self.program.name}">\n'
        chr_block += f"\t<chr_constraint> {', '.join(signatures)}\n"
        for rule in self.program.rules:
            chr_block += self._generate_rule(rule)

        chr_block += "\t</CHR>\n"
        chr_block += "*/"

        return chr_block

    @staticmethod
    def _generate_rule(rule: Rule) -> str:
        rule_str = "\t\t"
        if rule.name:
            rule_str += f"{rule.name} @ "
        else:
            rule_str += f"rule{rule._id} @ "  # noqa

        if rule.negative_head and rule.positive_head:
            rule_str += f"{CHRGenerator._format_head(rule.positive_head)} \\ {CHRGenerator._format_head(rule.negative_head)} <=> "
        elif rule.negative_head and not rule.positive_head:
            rule_str += f"{CHRGenerator._format_head(rule.negative_head)} <=> "
        elif rule.positive_head:
            rule_str += f"{CHRGenerator._format_head(rule.positive_head)} ==> "

        if rule.guard:
            guard_str = rule.guard.to_chrpp()
            rule_str += f"{guard_str} | "

        rule_str += CHRGenerator._format_body(rule.body)

        rule_str += ";;\n"
        return rule_str

    @staticmethod
    def generate_callback_registry_header() -> str:
        ret = ""
        ret += "#ifndef PYTHON_CALLBACK_REGISTRY_HH\n"
        ret += "#define PYTHON_CALLBACK_REGISTRY_HH\n"
        ret += "\n"
        ret += "#include <string>\n"

        ret += "#include <chrpp.hh>\n"
        ret += "#include <unordered_map>\n"
        ret += "#include <pybind11/pybind11.h>\n"
        ret += "\n"
        ret += "namespace py = pybind11;\n"
        ret += "\n"
        ret += 'class __attribute__((visibility("default"))) PythonCallbackRegistry {\n'
        ret += "    std::unordered_map<std::string, py::function> callbacks;\n"
        ret += "    \n"
        ret += "public:\n"
        ret += "    void register_function(const std::string& name, py::function func);\n"
        ret += "    template<typename... Args>\n"
        ret += "void call(const std::string& name, Args&&... args){\n"
        ret += "    py::gil_scoped_acquire acquire;\n"
        ret += "    auto it = callbacks.find(name);\n"
        ret += "    if (it != callbacks.end()) {\n"
        ret += "        it->second(std::forward<Args>(args)...);\n"
        ret += "    }\n"
        ret += "}\n"
        ret += "};\n"
        ret += "\n"
        ret += "namespace pybind11::detail {\n"
        ret += "    template<typename T>\n"
        ret += "    struct type_caster<chr::Logical_var<T>> {\n"

        ret += "        static handle cast(const chr::Logical_var<T>& src,\n"
        ret += "                          return_value_policy /* policy */,\n"
        ret += "                          handle /* parent */) {\n"
        ret += "            return py::cast(src.to_string()); // Or whatever accessor exists\n"
        ret += "        }\n"
        ret += "\n"

        ret += '        PYBIND11_TYPE_CASTER(chr::Logical_var<T>, _("LogicalVar[") +\n'
        ret += '                            type_caster<T>::name + _("]"));\n'
        ret += "    };\n"
        ret += "}\n"

        ret += "#endif // PYTHON_CALLBACK_REGISTRY_HH\n"
        return ret

    @staticmethod
    def generate_callback_registry_implementation(
        callback_registry_hh: Path | str,
    ) -> str:
        ret = ""
        ret += f"#include <{callback_registry_hh}>\n"
        ret += "\n"
        ret += "void PythonCallbackRegistry::register_function(const std::string& name, py::function func) {\n"
        ret += "    callbacks[name] = func;\n"
        ret += "}\n"
        ret += "\n"
        # ret += "void PythonCallbackRegistry::call(const std::string& name, Args&&... args){\n"
        # ret += "    py::gil_scoped_acquire acquire;\n"
        # ret += "    auto it = callbacks.find(name);\n"
        # ret += "    if (it != callbacks.end()) {\n"
        # ret += "        it->second();\n"
        # ret += "    }\n"
        # ret += "}\n"
        return ret

    def generate_chrpp(
        self,
    ) -> str:
        ret = ""
        ret += "#include <iostream>\n"
        ret += "#include <string>\n"
        ret += "#include <chrpp.hh>\n"
        if self.program._is_using_py_callback():  # noqa
            ret += f"#include <{self.program.python_registry_path}>\n"
        # ret += "\n"
        # ret += "inline void hello() {\n"
        # ret += '    std::cout << "Hello World" << std::endl;\n'
        # ret += "}\n"
        # ret += "\n"

        ret += self._generate_chr_block()

        return ret

    def generate_bindings(self) -> str:
        ret = ""
        ret += "#include <iostream>\n"
        ret += "#include <string>\n"
        ret += "#include <chrpp.hh>\n"
        ret += "#include <pybind11/pybind11.h>\n"
        ret += "#include <pybind11/stl.h>\n"
        ret += "#include <vector>\n"
        ret += "#include <unordered_map>\n"
        if self.program._is_using_py_callback():  # noqa
            ret += f"#include <{self.program.python_registry_path}>\n"

        ret += f"#include <{self.program.folder}/{self.program.name}-pychr{self.program.name}.hh>\n"
        ret += "namespace py = pybind11;\n"
        ret += "\n"

        ret += f"class {self.program.name}Wrapper {{\n"
        ret += "private:\n"
        ret += f"    chr::Shared_obj<{self.program.name}> space;\n"
        if self.program._is_using_py_callback():  # noqa
            ret += "        PythonCallbackRegistry registry;;\n"
        ret += "\n"
        ret += "public:\n"
        ret += f"    {self.program.name}Wrapper() {{\n"

        if self.program._is_using_py_callback():  # noqa
            ret += f"        space = {self.program.name}::create(registry);\n"
        else:
            ret += f"        space = {self.program.name}::create();\n"
        ret += "    }\n"
        ret += "\n"
        for cs in self.program.constraint_stores.values():
            ret += (
                "    " + CHRGenerator._constraint_store_add_function(cs) + "\n"
            )
            ret += "\n"
        if self.program._is_using_py_callback():  # noqa
            ret += "    void register_function(const std::string& name, py::function func) {\n"
            ret += "        registry.register_function(name, func);\n"
            ret += "    }\n"
            ret += "\n"
        ret += "    void reset() {\n"
        if self.program._is_using_py_callback():  # noqa
            ret += "        PythonCallbackRegistry registry;;\n"
            ret += f"        space = {self.program.name}::create(registry);\n"
        else:
            ret += f"        space = {self.program.name}::create();\n"
        ret += "    }\n"
        ret += "\n"
        ret += "    std::string get_store_string() {\n"
        ret += "        std::string result;\n"
        ret += "        auto it = space->chr_store_begin();\n"
        ret += "        while (!it.at_end()) {\n"
        ret += '            result += it.to_string() + "\\n";\n'
        ret += "            ++it;\n"
        ret += "        }\n"
        ret += "        return result;\n"
        ret += "    }\n"
        ret += "\n"
        ret += "    std::vector<std::string> get_constraint_store() {\n"
        ret += "        std::vector<std::string> result;\n"
        ret += "        auto it = space->chr_store_begin();\n"
        ret += "        while (!it.at_end()) {\n"
        ret += "            result.push_back(it.to_string());\n"
        ret += "            ++it;\n"
        ret += "        }\n"
        ret += "        return result;\n"
        ret += "    }\n"
        ret += "};\n"
        ret += "\n"

        ret += "\n"
        ret += "\n"
        ret += f"PYBIND11_MODULE({self.program.name}, m) {{\n"
        ret += f'    m.doc() = "Python bindings for {self.program.name} CHR program";\n'
        ret += "\n"
        ret += f'    py::class_<{self.program.name}Wrapper>(m, "{self.program.name}")\n'
        ret += "        .def(py::init<>())\n"
        ret += f'        .def("get_constraint_store", &{self.program.name}Wrapper::get_constraint_store,\n'
        ret += '                "Get constraint store as list of strings")\n'
        ret += f'        .def("reset", &{self.program.name}Wrapper::reset,\n'
        ret += '                "Reset the constraint store")\n'
        if self.program._is_using_py_callback():  # noqa
            ret += f'        .def("register_function", &{self.program.name}Wrapper::register_function,\n'
            ret += '                "Register a Python function with a name",\n'
            ret += '                py::arg("name"), py::arg("func"))\n'
        for cs in self.program.constraint_stores.values():
            ret += (
                "        "
                + CHRGenerator._constraint_store_wrapper_definition(
                    cs, self.program
                )
                + "\n"
            )
        ret += ";\n"
        ret += "}\n"
        return ret

    def generate_callback_registry_header_file(
        self, output_path: Path | str
    ) -> str:
        content = self.generate_callback_registry_header()
        Path(output_path).write_text(content)
        return content

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

    def generate_bindings_file(
        self,
        output_path: Path | str,
    ) -> str:
        content = self.generate_bindings()
        Path(output_path).write_text(content)
        return content
