#ifndef HELPER_CORE_HH
#define HELPER_CORE_HH

#include <cctype>
#include <iostream>
#include <memory>
#include <string>
#include <typeinfo>
#include <unordered_map>

#include <chrpp.hh>

class Arg {
public:
  virtual ~Arg() = default;
  virtual std::string type_name() const = 0;
};

template <typename T> class GroundArg : public Arg {
  T value;

public:
  GroundArg(T v) : value(v) {}
  T get_value() const { return value; }
  std::string type_name() const override { return typeid(T).name(); }
};

class LogicalVarArg : public Arg {
  std::string var_name;
  std::string expected_type;

public:
  LogicalVarArg(const std::string &name, const std::string &type)
      : var_name(name), expected_type(type) {}
  std::string get_var_name() const { return var_name; }
  std::string get_expected_type() const { return expected_type; }
  std::string type_name() const override { return expected_type; }
};

#endif // HELPER_CORE_HH
