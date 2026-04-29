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

X = program.symbol("X")  # Equivalent of importing Sym
Y = program.symbol("Y")

program.simpagation(
    positive_head=color(X), negative_head=color(Y), guard=X == Y, body=True
)

print(program.to_chrpp())

program.compile()

color.post("blue")
color.post("red")
color.post("brown")


print(program)
