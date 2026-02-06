#ifndef PYTHON_CALLBACK_REGISTRY_HH
#define PYTHON_CALLBACK_REGISTRY_HH

#include <chrpp.hh>
#include <iostream>
#include <pybind11/pybind11.h>
#include <string>
#include <unordered_map>

namespace py = pybind11;

class __attribute__((visibility("default"))) PythonCallbackRegistry {
  std::unordered_map<std::string, py::function> callbacks;

public:
  void register_function(const std::string &name, py::function func) {
    callbacks[name] = func;
  }
  template <typename... Args>
  void call(const std::string &name, Args &&...args) {
    py::gil_scoped_acquire acquire;
    auto it = callbacks.find(name);
    if (it != callbacks.end()) {
      it->second(std::forward<Args>(args)...);
    } else {
      std::cout << "Warning: Function '" << name
                << "' not found in callback registry." << std::endl;
      throw std::runtime_error("Function '" + name + "' not registered.");
    }
  }
};

namespace pybind11::detail {
template <typename T> struct type_caster<chr::Logical_var<T>> {
  static handle cast(const chr::Logical_var<T> &src, return_value_policy,
                     handle) {

    return py::cast(src.to_string());
  }

  PYBIND11_TYPE_CASTER(chr::Logical_var<T>,
                       _("LogicalVar[") + type_caster<T>::name + _("]"));
};
} // namespace pybind11::detail
#endif // PYTHON_CALLBACK_REGISTRY_HH
