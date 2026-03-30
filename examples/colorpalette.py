from chrpypy import Program

program = Program(
    "ColorPalette", "cp", compile_on="compile"
)  # Compile trigger allows us to control when the compilation occurs

red = program.constraint_store("red", [])
blue = program.constraint_store("blue", [])
yellow = program.constraint_store("yellow", [])
purple = program.constraint_store("purple", [])
orange = program.constraint_store("orange", [])
green = program.constraint_store("green", [])


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
