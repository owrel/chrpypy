from chrpypy import (
    SUCCESS,
    Program,
)

nb = 1000

p = Program(name="primes")

N = p.symbol("N")
X = p.symbol("X")
Y = p.symbol("Y")


candidate = p.constraint_store("candidate", (int,))
prime = p.constraint_store("prime", (int,))

p.simpagation(
    negative_head=candidate(N), guard=N > 1, body=[candidate(N - 1), prime(N)]
)

p.simpagation(
    negative_head=prime(X),
    positive_head=prime(Y),
    guard=(X % Y) == 0,
    body=SUCCESS,
)

candidate.post(nb)
print(p.statistics)
print(p.statistics.total_time)
print(f"Primes up to {nb}:", prime.get())
