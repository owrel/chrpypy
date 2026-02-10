#ifndef TYPE_CASTERS_HH
#define TYPE_CASTERS_HH

#include "helper_core.hh"
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace pybind11::detail {

template <> struct type_caster<std::shared_ptr<Arg>> {
public:
  PYBIND11_TYPE_CASTER(std::shared_ptr<Arg>, _("Arg"));

  bool load(handle src, bool convert) {
    if (py::isinstance<py::int_>(src)) {
      value = std::make_shared<GroundArg<int>>(src.cast<int>());
      return true;
    }
    if (py::isinstance<py::float_>(src)) {
      value = std::make_shared<GroundArg<double>>(src.cast<double>());
      return true;
    }
    if (py::isinstance<py::str>(src)) {
      std::string s = src.cast<std::string>();
      if (!s.empty() && std::isupper(static_cast<unsigned char>(s[0]))) {
        value = std::make_shared<LogicalVarArg>(s, "std::string");
        return true;
      }
      value = std::make_shared<GroundArg<std::string>>(s);
      return true;
    }
    if (py::isinstance<py::bool_>(src)) {
      value = std::make_shared<GroundArg<bool>>(src.cast<bool>());
      return true;
    }
    if (py::hasattr(src, "name")) {
      std::string var_name = src.attr("name").cast<std::string>();
      value = std::make_shared<LogicalVarArg>(var_name, "unknown");
      return true;
    }
    return false;
  }

  static handle cast(std::shared_ptr<Arg> src, return_value_policy policy,
                     handle parent) {
    if (!src)
      return py::none().release();
    return py::cast(src.get()).release();
  }
};

template <typename T> struct type_caster<chr::Logical_var<T>> {
public:
  PYBIND11_TYPE_CASTER(chr::Logical_var<T>, _("LogicalVar"));

  static handle cast(const chr::Logical_var<T> &src, return_value_policy policy,
                     handle parent) {
    return py::cast(src.to_string()).release();
  }

  bool load(handle src, bool convert) { return false; }
};

} // namespace pybind11::detail

#endif // TYPE_CASTERS_HH
