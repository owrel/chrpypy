#ifndef PYTHON_REGISTRY_HH
#define PYTHON_REGISTRY_HH

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

#endif // PYTHON_REGISTRY_HH
