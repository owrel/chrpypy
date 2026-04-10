from chrpypy import Program

program = Program(
    "ColorPalette", "cp", compile_on="compile"
)  # Compile trigger allows us to control when the compilation occurs

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

red.post()
print(blue.post())
print(purple)

print(program)
