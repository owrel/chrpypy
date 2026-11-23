from chrpypy import Program

program = Program(name="ParseRule", compile_on="compile")

leq = program.constraint("leq", (str, str))

program.parse_rule("reflexivity @ leq(X, X) <=> true ;;")
program.parse_rule("idempotence @ leq(X, Y) \\ leq(X, Y) <=> true ;;")
program.parse_rule("transitivity @ leq(X, Y), leq(Y, Z) ==> leq(X, Z)")

program.compile()

leq.post("lion", "zebra")
leq.post("zebra", "grass")
leq.post("bear", "grass")

print(program.store())
