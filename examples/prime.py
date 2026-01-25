from chrpypy import (
    SUCCESS,
    Program,
    PropagationRule,
    SimpagationRule,
    Variable,
)

N = Variable("N")
X = Variable("X")
Y = Variable("Y")

p = Program(name="primes")

candidate = p.constraint_store("candidate", (int,))
prime = p.constraint_store("prime", (int,))

p(
    PropagationRule(head=[candidate(1)], body=SUCCESS),
    PropagationRule(
        head=[candidate(N)],
        body=[candidate(N - 1), prime(N)],
    ),
    SimpagationRule(
        negative_head=[prime(Y)],
        positive_head=[prime(X)],
        guard=(X % Y) == 0,
        body=SUCCESS,
    ),
)


candidate.post(100)

print(p.statistics)
print(p.statistics.total_time)

print("Primes up to 30:", prime.get())
