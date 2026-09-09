from pathlib import Path

from lark import Lark

grm = Path("""
start : rule

rule : [name "@"] (simplification | propagation | simpagation) "."

simplification : head "<=>" [guard "|"] body
propagation : head "==>" [guard "|"] body
simpagation : head "\\" head "<=>" [guard "|"] body


head : chrconstraints
guard : builtinconstraints
body : goal

chrconstraints : chrconstraint | chrconstraint "," chrconstraint
builtinconstraints : builtin | builtin "," builtinconstraints
goal : chrconstraint  | chrconstraint "," goal

query : goal

builtin : eval_input
name : WORD
chrconstraint : WORD "(" _arg ")"
_arg : WORD | NUMBER | _arg "," _arg

%import common.NUMBER
%import common.WORD
%import common.WS
%ignore WS
%import python.eval_input

""")

parser = Lark(grm.read_text())
