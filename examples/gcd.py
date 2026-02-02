from chrpypy import (
    SUCCESS,
    Program,
    Variable,
)

p = Program(name="GCD", verbose="DEBUG", folder="gcd", use_cache=False)
gcd = p.constraint_store("gcd", (int,))

N = Variable("N")
M = Variable("M")

p.simpagation(negative_head=gcd(0), body=SUCCESS)
p.simpagation(
    negative_head=gcd(M),
    positive_head=gcd(N),
    guard=(N <= M),
    body=gcd(M - N),
)

gcd.post(182)
gcd.post(144)

print(p.statistics)
print(p.statistics.total_time)


print(f"GCD: {gcd.get()}")
