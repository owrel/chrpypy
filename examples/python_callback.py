import logging

from chrpypy import (
    SUCCESS,
    CompileTrigger,
    FunctionCall,
    Program,
    SimpagationRule,
)

logger = logging.getLogger(__name__)


p = Program(
    name="PyCallback",
    folder="pycallback",
    use_cache=True,
    compile_on=CompileTrigger.COMPILE,
)
cb = p.constraint_store("cb", (int,))

X = p.symbol("X")
p(
    SimpagationRule(
        negative_head=cb(X),
        body=[FunctionCall("value", X), SUCCESS],
    ),
)

p.compile()
p.register_function(
    "value",
    print,
)

cb.post(0)
logger.info(p.statistics)
logger.info(p.statistics.total_time)
