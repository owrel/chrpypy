from chrpypy.expressions import Unification

from chrpypy import SUCCESS, CompileTrigger, Program

p = Program(
    name="GCD", folder="gcd", use_cache=False, compile_on=CompileTrigger.COMPILE
)
gcd = p.constraint_store("gcd", (int,))
res = p.constraint_store("res", (int,))


N = p.symbol("N")
M = p.symbol("M")


p.simpagation(negative_head=gcd(0), body=SUCCESS)
p.simpagation(
    positive_head=gcd(N),
    negative_head=gcd(M),
    guard=(N <= M),
    body=gcd(M - N),
)
p.simpagation(
    positive_head=gcd(N), negative_head=res(M), body=Unification(M, N)
)
p.compile()
Res = p.logicalvar("Res", int)
gcd.post(182)
gcd.post(144)
res.post(Res)


print(f"GCD: {Res.get_value()}")
