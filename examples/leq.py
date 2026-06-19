# Goal: Model a partial order relation (leq/2) using CHR rules.
# Showcases reflexivity, antisymmetry, idempotence, and transitivity
# — the classic CHR "constraint solver for less-or-equal" example.

from chrpypy import SUCCESS, Program, Unification

program = Program(
    name="LEQ",
    folder="leq",
    compile_on="first_post",
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


leq.post("1", "2")
leq.post("1", "3")
leq.post("2", "5")

print(program.store())
