# Goal: Generate prime numbers up to a given limit using a CHR-encoded
# Sieve of Eratosthenes. Demonstrates simpagation rules that remove
# non-prime candidates.

from chrpypy import SUCCESS, Program

nb = 1000

program = Program(name="primes", folder="primes")

N, X, Y = program.symbols("N", "X", "Y")

candidate = program.constraint("candidate")
prime = program.constraint("prime", [int])

program.simpagation(
    negative_head=candidate(N), guard=N > 1, body=[candidate(N - 1), prime(N)]
)

program.simpagation(
    negative_head=prime(X),
    positive_head=prime(Y),
    guard=(X % Y) == 0,
    body=SUCCESS,
)

print(program)

candidate.post(nb)
print(f"Primes up to {nb}:", prime.get())
