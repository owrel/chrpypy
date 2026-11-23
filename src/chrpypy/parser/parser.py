import logging

from lark import Lark

logger = logging.getLogger(__name__)

# Notes on the grammar:
# - Keywords are declared as named terminals (PASSIVE, PERSISTENT, ...). With
#   Lark's default ``keep_all_tokens=False`` an anonymous string terminal is
#   dropped from the tree, which would make pragmas impossible to inspect.
# - Lists use ``item ("," item)*`` instead of right recursion so the resulting
#   tree is flat.
# - Python expressions are parsed by Python's own ``ast`` module later. The
#   grammar only needs to know where an expression starts and stops, which is
#   what the ``arg_expr`` / ``guard_expr`` wrappers and ``propagate_positions``
#   provide.
grm = r"""
start: chr_statement*

?chr_statement: chr_constraint_declarations | chr_rule

chr_constraint_declarations: "<chr_constraint>" constraint_declaration ("," constraint_declaration)*

constraint_declaration: NAME "(" [type_list] ")" pragmas_c

type_list: type_name ("," type_name)*
type_name: NAME

PERSISTENT: "persistent"
NO_REACTIVATE: "no_reactivate"
pragma_c_value: PERSISTENT | NO_REACTIVATE
pragma_c_list: pragma_c_value ("," pragma_c_value)*
pragmas_c:
    | "#" "{" pragma_c_list "}"
    | "#" pragma_c_value

// Rule definition
chr_rule: [rule_name] core_rule ";;"
rule_name: NAME "@"

?core_rule: propagation_rule | propagation_rule_noh | simplification_rule | simpagation_rule

propagation_rule: head "==>" guard body
propagation_rule_noh: head "=>>" guard body
simplification_rule: head "<=>" guard body
simpagation_rule: head "\\" head "<=>" guard body

// Head
head: head_constraint ("," head_constraint)*
head_constraint: constraint pragmas_h

PASSIVE: "passive"
NO_HISTORY: "no_history"
pragma_h_value: PASSIVE | NO_HISTORY
pragma_h_list: pragma_h_value ("," pragma_h_value)*
pragmas_h:
    | "#" "{" pragma_h_list "}"
    | "#" pragma_h_value

constraint: NAME "(" [arg_list] ")"

arg_list: arg_expr ("," arg_expr)*
arg_expr: test

// Guard
guard: guard_constraints "|"
    |
guard_constraints: guard_expr ("," guard_expr)*
guard_expr: test

// Body
body: body_constraints

body_constraints: body_constraint (("," | ";") body_constraint)*
body_constraint: "(" body_constraints ")" | body_atom | body_literal
body_atom: constraint pragmas_r

TRUE_LIT: "true"
FALSE_LIT: "false"
SUCCESS_LIT: "success"
FAILURE_LIT: "failure"
body_literal_value: TRUE_LIT | FALSE_LIT | SUCCESS_LIT | FAILURE_LIT
body_literal: body_literal_value

CATCH_FAILURE: "catch_failure"
pragmas_r:
    | "#" CATCH_FAILURE pragmas_r

%import common.WS
%ignore WS
%import python.NAME
%import python.test
"""

parser = Lark(
    grm,
    parser="earley",
    propagate_positions=True,
    maybe_placeholders=True,
)
