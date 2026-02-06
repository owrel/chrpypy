from time import sleep

from chrpypy.constraints import Constraint
from chrpypy.expressions import Constant

from chrpypy import ANON, Program

p = Program(
    name="ConwayLife",
    folder="conway",
)


x_size = -20, 20
y_size = -20, 20


cell = p.constraint_store("cell", (int, int))
next_gen_cell = p.constraint_store("next_gen_cell", (int, int))

count = p.constraint_store("count", (int, int, int, bool))
neighbor = p.constraint_store("neighbor", (int, int, int, int))

tick = p.constraint_store("tick", ())
tick_count = p.constraint_store("tick_count", ())
tick_gen = p.constraint_store("tick_gen", ())
tick_clear = p.constraint_store("tick_clear", ())
tick_next = p.constraint_store("tick_next", ())


# X = Variable("X")
X_ = Variable("X_")

Y = Variable("Y")
Y_ = Variable("Y_")
C = Variable("C")
C_ = Variable("C_")

K = Variable("K")


for dx in [-1, 0, 1]:
    for dy in [-1, 0, 1]:
        if dx == 0 and dy == 0:
            continue

        p.simpagation(
            positive_head=[cell(X, Y)],
            guard=[
                X + dx >= x_size[0],
                X + dx <= x_size[1],
                Y + dy >= y_size[0],
                Y + dy <= y_size[1],
            ],
            body=[
                neighbor(X, Y, X + dx, Y + dy),
            ],
        )


p.simpagation(
    positive_head=[cell(X, Y)],
    body=[count(X, Y, 0, True)],
)

p.simpagation(
    positive_head=[neighbor(ANON, ANON, Constant(0), Y)],
    body=[count("X", Y, 0, False)],
)

p.simpagation(
    negative_head=[count(X, Y, 0, False)],
    positive_head=[count(X, Y, 0, True), cell(X, Y)],
)

p.simpagation(
    positive_head=count(X, Y, 0, False), negative_head=count(X, Y, 0, False)
)

p.simpagation(
    negative_head=[count(X, Y, C_, False), count(X, Y, 0, True)],
    body=count(X, Y, 0, True),
)


p.simpagation(negative_head=tick(), body=tick_count())


p.simpagation(
    negative_head=[count(X, Y, C, True), neighbor(X, Y, X_, Y_)],
    positive_head=[cell(X, Y), cell(X_, Y_), tick_count()],
    body=[count(X, Y, C + 1, True)],
)

p.simpagation(
    negative_head=[
        count(X_, Y_, C, False),
        neighbor(X, Y, X_, Y_),
    ],
    positive_head=[cell(X, Y), tick_count()],
    body=[count(X_, Y_, C + 1, False)],
)


p.simpagation(
    negative_head=[count(X, Y, C, K), count(X, Y, C_, K)],
    positive_head=tick_count(),
    body=count(X, Y, C + C_, K),
)

p.simpagation(negative_head=tick_count(), body=tick_gen())


# Rules for creating next generation cells based on Conway's Game of Life rules

# Rule 1: A live cell with 2 or 3 neighbors survives
p.simpagation(
    positive_head=[count(X, Y, C, True), tick_gen()],
    guard=[C >= 2, C <= 3],
    body=[next_gen_cell(X, Y)],
)


# Rule 2: A dead cell with exactly 3 neighbors becomes alive
p.simpagation(
    positive_head=[count(X, Y, 3, False), tick_gen()],
    body=[next_gen_cell(X, Y)],
)

p.simpagation(negative_head=tick_gen(), body=tick_clear())


p.simpagation(positive_head=tick_clear(), negative_head=[count(X, Y, C, K)])
p.simpagation(positive_head=tick_clear(), negative_head=[cell(X, Y)])
p.simpagation(negative_head=tick_clear(), body=tick_next())

p.simpagation(
    positive_head=tick_next(),
    negative_head=[next_gen_cell(X, Y)],
    body=[cell(X, Y)],
)
p.simpagation(negative_head=tick_next())

p.compile()


def show_grid(cells: list[Constraint]):
    grid = [
        ["  " for _ in range(x_size[1] - x_size[0] + 1)]
        for _ in range(y_size[1] - y_size[0] + 1)
    ]

    for x, y in cells:
        grid[y - y_size[0]][x - x_size[0]] = "██"

    width = len(grid[0])
    print(" _" + "_" * (width * 2) + "_")
    for row in grid:
        print("| " + "".join(row) + " |")
    print(" ‾" + "‾" * (width * 2) + "‾")


cell.post(-1, 0)
cell.post(1, 0)
cell.post(1, 1)
cell.post(0, 1)
cell.post(0, 2)


# print(p.rules[0].to_str())

for x in range(200):
    print(f"Generation {x}")
    show_grid(cell.get())
    tick.post()
    sleep(0.08)

# print(p.statistics.execution_time)
