from chrpypy import Program

program = Program(
    "ColorPalette", "cp", compile_on=Program.compile_trigger.COMPILE
)
color = program.constraint_store("color")


program.simplification(
    name="redplusblue",
    negative_head=[color("red"), color("blue")],
    body=[color("purple")],
)


program._set_reset_systems(color)

program.compile()
color.post("red")
color.post("blue")

print(color.get())
print(program.compiled)
print(color.reset())
color.post("blue")

print(program.get_constraints())
