from chrpypy import (
    SUCCESS,
    FunctionCall,
    Program,
    SimpagationRule,
    Variable,
)

p = Program(
    name="PyCallback", verbose="DEBUG", folder="pycallback", use_cache=False
)
cb = p.constraint_store("cb", (int,))

X = Variable("X")
p(
    SimpagationRule(
        negative_head=cb(X),
        body=[FunctionCall("value", X), SUCCESS],
    ),
)

p.register_function("value", lambda x: print(f"You entered value {x}"))
print(p.statistics)
print(p.statistics.total_time)
cb.post(0)
