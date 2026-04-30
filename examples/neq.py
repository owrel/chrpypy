from chrpypy import FAILURE, SUCCESS, Constant, Ground, Program, Unification

program = Program("inequality", "inequality", compile_on="compile")

neq = program.constraint("neq", [int, int])
X = program.symbol("X")
Y = program.symbol("Y")


program.simplification(negative_head=neq(X, X), body=FAILURE)

program.propagation(positive_head=neq(X, Y), body=Unification(X, Constant(1)))

program.simplification(
    negative_head=neq(X, Y),
    guard=Ground(X) & Ground(Y) & (X != Y),
    body=SUCCESS,
)

program.compile()

# neq.post(10, 11)
# print(neq)


A = program.logicalvar("A", int)
B = program.logicalvar("B", int)
program.post(neq(A, B))

# print(dir(program._compiler.wrapper))

# print(program)
# print(program._compiler.wrapper.unify_logical_var_int("A", "B"))
# print(program)


print(A.get_value(), B.get_value())
