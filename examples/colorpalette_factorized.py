# Goal: Demonstrate color mixing using a factorized constraint representation.
# A single parameterized `color/1` constraint represents all colors,
# with rules that combine two colors into a third (e.g., red + blue -> purple).
# Also shows ANON (anonymous variable) usage and duplicate removal.

from chrpypy import ANON, Program

program = Program("ColorPalette", "cpf", compile_on="compile")

color = program.constraint("color", [str])

program.simplification(
    negative_head=[color("red"), color("blue")], body=color("purple")
)
program.simplification(
    negative_head=[color("red"), color("yellow")], body=color("orange")
)
program.simplification(
    negative_head=[color("blue"), color("yellow")], body=color("green")
)

program.simpagation(
    positive_head=color("brown"), negative_head=color(ANON), body=True
)

X, Y = program.symbols("X", "Y")

program.simpagation(
    positive_head=color(X), negative_head=color(Y), guard=X == Y, body=True
)

program.compile()

color.post("blue")
color.post("red")
color.post("brown")

print(program.store())
