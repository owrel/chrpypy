# Goal: Model a piggy bank that sums coins when they are added together.
# Shows how CHR simplification rules can reduce multiple constraints
# into one by combining their integer arguments (I + J -> summed coin).

from chrpypy import Program

program = Program("bank", "bk", compile_on="compile")

I, J = program.symbols("I", "J")  # noqa

piggy_bank = program.constraint("piggy_bank", [int])

program.simplification(
    name="sum",
    negative_head=[piggy_bank(I), piggy_bank(J)],
    body=[piggy_bank(I + J)],
)

program.compile()
