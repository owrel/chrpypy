# Goal: Compute the greatest common divisor (GCD) of two integers using
# the Euclidean algorithm encoded as CHR rules. Demonstrates logical
# variables and the Unification mechanism for retrieving results.

from chrpypy import SUCCESS, Program, Unification

program = Program(name="GCD", folder="gcd", compile_on="compile")
gcd = program.constraint("gcd", (int,))
res = program.constraint("res", (int,))

N, M = program.symbols("N", "M")

program.simpagation(negative_head=gcd(0), body=SUCCESS)
program.simpagation(
    positive_head=gcd(N),
    negative_head=gcd(M),
    guard=(N <= M),
    body=gcd(M - N),
)
program.simpagation(
    positive_head=gcd(N), negative_head=res(M), body=Unification(M, N)
)

program.compile()
Res = program.logicalvar("Res", int)
gcd.post(182)
gcd.post(144)
res.post(Res)

print(f"GCD: {Res.value()}")
