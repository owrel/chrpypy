from chrpypy import (
    SUCCESS,
    Program,
)

nb = 1000

p = Program(name="primes", folder="primes")

N = p.symbol("N")
X = p.symbol("X")
Y = p.symbol("Y")


candidate = p.constraint("candidate")
prime = p.constraint("prime", [int])

print(prime)

p.simpagation(
    negative_head=candidate(N), guard=N > 1, body=[candidate(N - 1), prime(N)]
)

p.simpagation(
    negative_head=prime(X),
    positive_head=prime(Y),
    guard=(X % Y) == 0,
    body=SUCCESS,
)

print(prime)
candidate.post(nb)
print(p._statistics)
print(p._statistics.total_time)
print(f"Primes up to {nb}:", prime.get())
