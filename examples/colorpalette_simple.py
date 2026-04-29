from chrpypy import Program

program = Program("ColorPalette", "cps", compile_on="compile")

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

print(program._rules)

# program.compile()

# red.post()
# print(blue.post())
# print(purple)

# print(program)
