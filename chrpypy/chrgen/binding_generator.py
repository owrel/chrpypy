from typing import TYPE_CHECKING

from ..typesystem import TypeSystem

if TYPE_CHECKING:
    from ..constraints import ConstraintStore
    from ..program import Program


class BindingGenerator:
    def __init__(self, program: "Program"):
        self.program = program

    def generate_bindings_includes(self) -> str:
        includes = """
            #include <pybind11/pybind11.h>
            #include <chrpp.hh>
            #include <iostream>s
            #include <string>
            #include <any>
            #include <pybind11/stl.h>
            #include <vector>
            #include <unordered_map>
            #include <typeinfo>
        """

        includes += f"#include <{self.program.compiler.current_hash_folder / self.program.name}-pychr{self.program.name}.hh>\n"

        if self.program._retrieve_callbacks():
            includes += f"#include <{self.program.helper_hh}>\n"
        else:
            includes += f"#include <{self.program.helper_core_hh}>\n"

        includes += "namespace py = pybind11;\n\n"
        return includes

    def _generate_wrapper_class_private_members(self) -> str:
        wrapper_class = f"class {self.program.name}Wrapper {{\n"
        wrapper_class += "private:\n"
        wrapper_class += f"    chr::Shared_obj<{self.program.name}> space;\n"

        if self.program._retrieve_callbacks():
            wrapper_class += "    PythonCallbackRegistry registry;\n"

        for python_type in TypeSystem.python_types():
            cpp_type = TypeSystem.python_to_cpp(python_type)
            wrapper_class += f"    std::unordered_map<std::string, chr::Logical_var<{cpp_type}>> logical_vars_{python_type.__name__};\n"

        wrapper_class += "\n"
        return wrapper_class

    def _generate_wrapper_class_methods(self) -> str:
        methods = self._generate_logical_var_getters()
        methods += self._generate_py_to_arg_method()
        methods += self._generate_resolve_arg_method()
        methods += self._generate_constructor()
        methods += self._generate_logical_var_setters()
        methods += self._generate_constraint_adders()
        methods += self._generate_utility_methods()
        return methods

    def _generate_logical_var_getters(self) -> str:
        getters = ""
        for python_type in TypeSystem.python_types():
            cpp_type = TypeSystem.python_to_cpp(python_type)
            getters += f"""
                chr::Logical_var<{cpp_type}> get_logical_var_{python_type.__name__}_impl(const std::string& name) {{
                    auto it = logical_vars_{python_type.__name__}.find(name);
                    if (it == logical_vars_{python_type.__name__}.end()) {{
                        throw std::runtime_error("Logical variable '" + name + "' of type {cpp_type} not found");
                    }}
                    return it->second;
                }}
                """
        return getters

    def _generate_py_to_arg_method(self) -> str:
        return """
            std::shared_ptr<Arg> py_to_arg(py::handle obj) {
                if (py::isinstance<py::int_>(obj)) {
                    return std::make_shared<GroundArg<int>>(obj.cast<int>());
                }
                if (py::isinstance<py::float_>(obj)) {
                    return std::make_shared<GroundArg<double>>(obj.cast<double>());
                }
                if (py::isinstance<py::str>(obj)) {
                    std::string s = obj.cast<std::string>();
                    return std::make_shared<GroundArg<std::string>>(s);
                }
                if (py::isinstance<py::bool_>(obj)) {
                    return std::make_shared<GroundArg<bool>>(obj.cast<bool>());
                }
                if (py::hasattr(obj, "name")) {
                    std::string var_name = obj.attr("name").cast<std::string>();
                    return std::make_shared<LogicalVarArg>(var_name, "unknown");
                }
                throw std::runtime_error("Unsupported Python type: " + std::string(py::str(obj).cast<std::string>()));
            }
            """

    def _generate_resolve_arg_method(self) -> str:
        resolve_arg_method = """
            template<typename T>
            chr::Logical_var<T> resolve_arg(const Arg& arg, int position, const std::string& expected_type) {
                if (auto* ground = dynamic_cast<const GroundArg<T>*>(&arg)) {
                    return chr::Logical_var<T>(ground->get_value());
                }
                if (auto* logical = dynamic_cast<const LogicalVarArg*>(&arg)) {
                    std::string var_type = logical->get_expected_type();
                    if (var_type == "unknown") {
                        var_type = expected_type;
                    }
                    if (var_type != expected_type) {
                        throw std::runtime_error("Type mismatch at position " + std::to_string(position) +
                                                ": expected " + expected_type + ", got " + var_type);
                    }
            """

        python_types = TypeSystem.python_types()
        for i, python_type in enumerate(python_types):
            cpp_type = TypeSystem.python_to_cpp(python_type)
            if i == 0:
                resolve_arg_method += (
                    f"        if constexpr (std::is_same_v<T, {cpp_type}>) {{\n"
                )
            else:
                resolve_arg_method += f"        else if constexpr (std::is_same_v<T, {cpp_type}>) {{\n"

            resolve_arg_method += f"            return get_logical_var_{python_type.__name__}_impl(logical->get_var_name());\n"
            resolve_arg_method += "        }\n"

        resolve_arg_method += """        else {
                        throw std::runtime_error("Unsupported type at position " + std::to_string(position));
                    }
                }
                throw std::runtime_error("Invalid argument type at position " + std::to_string(position));
            }
            """
        return resolve_arg_method

    def _generate_constructor(self) -> str:
        constructor = "public:\n"
        constructor += f"    {self.program.name}Wrapper() {{\n"
        if self.program._retrieve_callbacks():
            constructor += (
                f"        space = {self.program.name}::create(registry);\n"
            )
        else:
            constructor += f"        space = {self.program.name}::create();\n"
        constructor += "    }\n\n"
        return constructor

    def _generate_logical_var_setters(self) -> str:
        setters = ""
        for python_type in TypeSystem.python_types():
            cpp_type = TypeSystem.python_to_cpp(python_type)
            setters += f"    chr::Logical_var<{cpp_type}> get_logical_var_{python_type.__name__}(const std::string& name) {{\n"
            setters += f"        return get_logical_var_{python_type.__name__}_impl(name);\n"
            setters += "    }\n\n"

        for python_type in TypeSystem.python_types():
            cpp_type = TypeSystem.python_to_cpp(python_type)
            setters += f"    void set_logical_var_{python_type.__name__}(const std::string& name) {{\n"
            setters += f"        logical_vars_{python_type.__name__}[name] = chr::Logical_var<{cpp_type}>();\n"
            setters += "    }\n\n"
        return setters

    def _generate_constraint_adders(self) -> str:
        adders = ""
        for cs in self.program.constraint_stores.values():
            if len(cs.types) == 0:
                adders += f"void add_{cs.name}() {{ space->{cs.name}(); }}\n\n"
            else:
                adders += self._generate_constraint_adder_for_store(cs)

        return adders

    def _generate_constraint_adder_for_store(
        self, cs: "ConstraintStore"
    ) -> str:
        params = ", ".join(
            f"py::object arg{idx}" for idx in range(len(cs.types))
        )
        signature = f"void add_{cs.name}_py({params})"

        body_lines = []
        for idx, python_t in enumerate(cs.types):
            cpp_type = TypeSystem.python_to_cpp(python_t)
            body_lines.extend(
                [
                    f"std::shared_ptr<Arg> arg{idx}_arg = py_to_arg(arg{idx});",
                    f'chr::Logical_var<{cpp_type}> lv{idx} = resolve_arg<{cpp_type}>(*arg{idx}_arg, {idx}, "{cpp_type}");',
                ]
            )

        call_args = ", ".join(f"lv{idx}" for idx in range(len(cs.types)))
        body_lines.append(f"space->{cs.name}({call_args});")

        body = "\n".join(f"    {line}" for line in body_lines)
        return f"{signature} {{\n{body}\n}}\n\n"

    def _generate_utility_methods(self) -> str:
        methods = ""

        if self.program._retrieve_callbacks():
            methods += """
            void register_function(const std::string& name, py::function func) {
                registry.register_function(name, func);
            }
            """

        methods += self._generate_reset_method()
        methods += self._generate_store_methods()
        methods += "};\n"
        return methods

    def _generate_reset_method(self) -> str:
        reset_method = "void reset() {\n"
        if self.program._retrieve_callbacks():
            reset_method += "        PythonCallbackRegistry registry;\n"
            reset_method += (
                f"        space = {self.program.name}::create(registry);\n"
            )
        else:
            reset_method += f"        space = {self.program.name}::create();\n"

        for python_type in TypeSystem.python_types():
            reset_method += (
                f"        logical_vars_{python_type.__name__}.clear();\n"
            )
        reset_method += "    }\n\n"
        return reset_method

    def _generate_store_methods(self) -> str:
        return """
            std::string get_store_string() {
                std::string result;
                auto it = space->chr_store_begin();
                while (!it.at_end()) {
                    result += it.to_string() + "\\n";
                    ++it;
                }
                return result;
            }

            std::vector<std::string> get_constraint_store() {
                std::vector<std::string> result;
                auto it = space->chr_store_begin();
                while (!it.at_end()) {
                    result.push_back(it.to_string());
                    ++it;
                }
                return result;
            }
        """

    def generate(self) -> str:
        code = self.generate_bindings_includes()

        code += self._generate_wrapper_class_private_members()
        code += self._generate_wrapper_class_methods()
        code += self._generate_pybind_module()

        return code

    def _generate_pybind_module(self) -> str:
        module = f"""
        PYBIND11_MODULE({self.program.name}, m) {{
            m.doc() = "Python bindings for {self.program.name} CHR program";

            py::class_<{self.program.name}Wrapper>(m, "{self.program.name}")
                .def(py::init<>())
                .def("get_constraint_store", &{self.program.name}Wrapper::get_constraint_store,
                     "Get constraint store as list of strings")
                .def("reset", &{self.program.name}Wrapper::reset,
                     "Reset the constraint store")
        """

        for python_type in TypeSystem.python_types():
            cpp_type = TypeSystem.python_to_cpp(python_type)
            module += f"""        .def("get_logical_var_{python_type.__name__}", &{self.program.name}Wrapper::get_logical_var_{python_type.__name__},
                     "Get logical variable of type {cpp_type} by name",
                     py::arg("name"))
                .def("set_logical_var_{python_type.__name__}", &{self.program.name}Wrapper::set_logical_var_{python_type.__name__},
                     "Create and store a logical variable of type {cpp_type} with given name ",
                     py::arg("name"))\n"""

        if self.program._retrieve_callbacks():
            module += f"""
                .def("register_function", &{self.program.name}Wrapper::register_function,
                     "Register a Python function with a name",
                     py::arg("name"), py::arg("func"))
            """

        for cs in self.program.constraint_stores.values():
            module += self._generate_constraint_binding(cs)

        module += ";\n}\n"
        return module

    def _generate_constraint_binding(self, cs: "ConstraintStore") -> str:
        if len(cs.types) > 0:
            args = ", ".join(f'py::arg("arg{i}")' for i in range(len(cs.types)))
            return f"""        .def("add_{cs.name}", &{self.program.name}Wrapper::add_{cs.name}_py,
                     "Add {cs.name} constraint", {args})\n"""
        return f"""        .def("add_{cs.name}", &{self.program.name}Wrapper::add_{cs.name},
                     "Add {cs.name} constraint")\n"""
