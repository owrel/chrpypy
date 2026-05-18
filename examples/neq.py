from chrpypy import FAILURE, SUCCESS, Constant, Ground, Program, Unification

program = Program(name="inequality", folder="inequality", compile_on="compile")

neq = program.constraint("neq", [int, int])
X = program.symbol("X")
Y = program.symbol("Y")


program.simplification(negative_head=neq(X, X), body=FAILURE)


program.simplification(
    negative_head=neq(X, Y),
    guard=Ground(X) & Ground(Y) & (X != Y),
    body=SUCCESS,
)

program.compile()
# neq.post(10, 11)
# print(neq)

# print(Ground(X) & Ground(Y) & (X != Y))

# print(dir(program._compiler.wrapper))

# print(program)
# print(program._compiler.wrapper.unify_logical_var_int("A", "B"))
# print(program)


neq.post(2, 2)
print(program)
print(program.reset_program())
print(neq.post(2, 4))
A = program.logicalvar("A", int)
B = program.logicalvar("B", int)
print(neq.post(A, B))
