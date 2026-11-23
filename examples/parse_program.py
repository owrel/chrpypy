from chrpypy.parser import parse_program

source = """
<chr_constraint> leq(str, str)

reflexivity @ leq(X, X) <=> true ;;
idempotence @ leq(X, Y) \\ leq(X, Y) <=> true ;;
transitivity @ leq(X, Y), leq(Y, Z) ==> leq(X, Z) ;;
"""

program = parse_program(source, name="ParseProgram")

leq = program.get_constraint("leq")

program.compile()

leq.post("lion", "zebra")
leq.post("zebra", "grass")
leq.post("bear", "grass")

print(program.store())
