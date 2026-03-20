from chrpypy import Program

program = Program(
    "ColorPalette", "cp", compile_on=Program.compile_trigger.COMPILE
)
color = program.constraint_store("color", [str])


program.simplification(
    name="redplusblue",
    negative_head=[color("red"), color("blue")],
    body=[color("purple")],
)

program.compile()
color.post("red")
color.post("blue")

print(color.get())
