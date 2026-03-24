from chrpypy import Constant, Program

program = Program(
    "ColorPalette", "cp", compile_on=Program.compile_trigger.COMPILE
)  # Compile trigger allows us to control when the compilation occurs
print(program)

color = program.constraint_store(
    "color", [str]
)  # We define here the name of the constraint store (and the name of following generated constraints) and the arity and types
print(color)


program.simplification(
    name="purple",
    negative_head=[color(Constant("red")), color(Constant("blue"))],
    body=[color(Constant("purple"))],
)

program.simplification(
    name="orange",
    negative_head=[color(Constant("red")), color(Constant("yellow"))],
    body=[color(Constant("orange"))],
)

program.simplification(
    name="green",
    negative_head=[color(Constant("blue")), color(Constant("yellow"))],
    body=[color(Constant("green"))],
)

program.compile()
