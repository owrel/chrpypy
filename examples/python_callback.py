import logging

from chrpypy import (
    SUCCESS,
    CompileTrigger,
    FunctionCall,
    Program,
)

logger = logging.getLogger(__name__)


p = Program(
    name="PyCallback",
    folder="pycallback",
    use_cache=True,
    compile_on=CompileTrigger.COMPILE,
)
cb = p.constraint("cb", (int,))

X = p.symbol("X")
p.simpagation(
    negative_head=cb(X),
    body=[FunctionCall("value", X), SUCCESS],
)

p.compile()
p.register_function(
    "value",
    print,
)

cb.post(0)
logger.info(p._statistics)
logger.info(p._statistics.total_time)
