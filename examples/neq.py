# Goal: Model inequality (neq/2) between integers using CHR rules.
# Shows how to express failure (X != X) and prove equality when
# both arguments are ground and different.

from chrpypy import FAILURE, SUCCESS, Ground, Program

program = Program(name="inequality", folder="inequality", compile_on="compile")

neq = program.constraint("neq", [int, int])
X, Y = program.symbols("X", "Y")

program.simplification(negative_head=neq(X, X), body=FAILURE)

program.simplification(
    negative_head=neq(X, Y),
    guard=Ground(X) & Ground(Y) & (X != Y),
    body=SUCCESS,
)

program.compile()

neq.post(2, 2)
print(program)
print(program.reset_program())
print(neq.post(2, 4))
A = program.logicalvar("A", int)
B = program.logicalvar("B", int)
print(neq.post(A, B))
