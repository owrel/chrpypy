# Goal: Demonstrate calling Python functions directly from CHR rules
# via the FunctionCall mechanism. Shows how to register a Python
# callback and trigger it when a constraint is removed.

import logging

from chrpypy import SUCCESS, Program

logger = logging.getLogger(__name__)

program = Program(
    name="PyCallback",
    folder="pycallback",
    use_cache=True,
    compile_on="compile",
)
cb = program.constraint("cb", (int,))

X = program.symbol("X")

program.simpagation(
    negative_head=cb(X),
    body=[program.function(print, X), SUCCESS],
)

program.compile()

cb.post(0)
