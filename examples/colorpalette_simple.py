# Goal: Demonstrate color mixing using simple nullary constraints.
# Each color is a separate constraint with no arguments.
# Rules specify how pairs of colors combine into a new color.

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

program.compile()

red.post()
blue.post()

print(program.store())
