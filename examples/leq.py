# Goal: Model a partial order relation (leq/2) using CHR rules.
# Showcases reflexivity, antisymmetry, idempotence, and transitivity
# — the classic CHR "constraint solver for less-or-equal" example.

from chrpypy import SUCCESS, Program, Unification

program = Program(
    name="LEQ",
)
leq = program.constraint("leq", lazy=True)

X, Y, Z = program.symbols("X", "Y", "Z")

program.simplification(
    name="reflexivity", negative_head=leq(X, X), body=SUCCESS
)
program.simplification(
    name="antisymmetry",
    negative_head=[leq(X, Y), leq(Y, X)],
    body=Unification(X, Y),
)
program.simpagation(
    name="idempotence",
    positive_head=leq(X, Y),
    negative_head=leq(X, Y),
    body=SUCCESS,
)
program.propagation(
    name="transitivity", positive_head=[leq(X, Y), leq(Y, Z)], body=leq(X, Z)
)

# Food chain leq(predator, prey)
leq.post("lion", "zebra")
leq.post("zebra", "grass")
leq.post("bear", "grass")

print(program.store())
