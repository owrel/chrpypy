from chrpypy import SUCCESS, Program, Unification, Variable

p = Program(
    name="LEQ",
    folder="leq",
    verbose="DEBUG",
    compile_on="FIRST_POST",
    use_cache=False,
)
leq = p.constraint_store("leq", (int, int))

X = Variable("X")
Y = Variable("Y")
Z = Variable("Z")


p.simplification(name="reflexivity", negative_head=leq(X, X), body=SUCCESS)
p.simplification(
    name="antisymmetry",
    negative_head=[leq(X, Y), leq(Y, X)],
    body=Unification(X, Y),
)
p.simpagation(
    name="idempotence",
    positive_head=leq(X, Y),
    negative_head=leq(X, Y),
    body=SUCCESS,
)
p.propagation(
    name="transitivity", positive_head=[leq(X, Y), leq(Y, Z)], body=leq(X, Z)
)

p.compile()

leq.post(1, 2)
leq.post(2, 3)
leq.post(2, 5)
print(leq.get())
