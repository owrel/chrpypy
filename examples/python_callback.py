import logging

from chrpypy import (
    SUCCESS,
    FunctionCall,
    Program,
    SimpagationRule,
    Variable,
)

logger = logging.getLogger(__name__)


p = Program(
    name="PyCallback",
    verbose="DEBUG",
    folder="pycallback",
    use_cache=True,
    compile_on="compile",
)
cb = p.constraint_store("cb", (int,))

X = Variable("X")
p(
    SimpagationRule(
        negative_head=cb(X),
        body=[FunctionCall("value", X), SUCCESS],
    ),
)

p.compile()
p.register_function(
    "value",
    lambda x: print(x),
)

cb.post(0)
logger.info(p.statistics)
logger.info(p.statistics.total_time)
