from chrpypy import (
    SUCCESS,
    Program,
    Variable,
)

nb = 1000

N = Variable("N")
X = Variable("X")
Y = Variable("Y")

p = Program(name="primes")

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
