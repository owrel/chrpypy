from chrpypy import (
    SUCCESS,
    Program,
    SimpagationRule,
    Variable,
)

p = Program(name="GCD", verbose="DEBUG", folder="gcd", use_cache=False)
gcd = p.constraint_store("gcd", (int,))

N = Variable("N")
M = Variable("M")

p(
    SimpagationRule(
        negative_head=gcd(0),
        body=SUCCESS,
    ),
    SimpagationRule(
        negative_head=gcd(N),
        positive_head=gcd(M),
        guard=(N <= M),
        body=gcd(M - N),
    ),
)


gcd.post(182)
gcd.post(144)

print(p.statistics)
print(p.statistics.total_time)


print(f"GCD: {gcd.get()}")
