from chrpypy import Program

program = Program("ColorPalette", "cp", compile_on="compile")

red = program.constraint("red", [])
blue = program.constraint("blue", [])
yellow = program.constraint("yellow", [])
purple = program.constraint("purple", [])
orange = program.constraint("orange", [])
green = program.constraint("green", [])


program.simplification(
    name="purple",
    negative_head=[red(), blue()],
    body=[purple()],
)

program.simplification(
    name="orange",
    negative_head=[red(), yellow()],
    body=[orange()],
)

program.simplification(
    name="green",
    negative_head=[blue(), yellow()],
    body=[green()],
)

program.compile()

blue.post()
red.post()

print(program)

program = Program("transmutation", folder="./transmu", compile_on="compile")

philosopher_stone = program.constraint("philosopher_stone", [])
lead = program.constraint("lead", [])
gold = program.constraint("gold", [])

program.simpagation(
    positive_head=philosopher_stone(), negative_head=lead(), body=gold()
)

program.compile()

philosopher_stone.post()
lead.post()

print(program)


program = Program("bank", "bk", compile_on="compile")

I = program.symbol(name="I")
J = program.symbol(name="J")


piggy_bank = program.constraint("piggy_bank", [int])

program.simplification(
    name="sum",
    negative_head=[piggy_bank(I), piggy_bank(J)],
    body=[piggy_bank(I + J)],
)


program.compile()
