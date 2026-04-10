from chrpypy import Program
from chrpypy import Symbol as Sym

program = Program("bank", "bk", compile_on="compile")

I = Sym(name="I")
J = Sym(name="J")


piggy_bank = program.constraint("piggy_bank", [int])

program.simplification(
    name="sum",
    negative_head=[piggy_bank(I), piggy_bank(J)],
    body=[piggy_bank(I + J)],
)


program.compile()
