# ruff : noqa :  FBT003
import operator
from time import sleep

import chrpypy
from chrpypy import ANON, Constraint, Inline


def show_grid(cells: list[Constraint]):
    min_x = min(cells, key=operator.itemgetter(0))[0]
    min_y = min(cells, key=operator.itemgetter(1))[1]
    max_x = max(cells, key=operator.itemgetter(0))[0] + 1
    max_y = max(cells, key=operator.itemgetter(1))[1] + 1

    grid = [["  " for _ in range(min_x, max_x)] for _ in range(min_y, max_y)]

    for x, y, s in cells:
        if s:
            grid[y - min_y][x - min_x] = "██"

    width = len(grid[0])
    print(" _" + "_" * (width * 2) + "_")
    for row in grid:
        print("| " + "".join(row) + " |")
    print(" ‾" + "‾" * (width * 2) + "‾")


p = chrpypy.Program("conway_v2", "cv2", auto_reset_rules=False)

cell = p.constraint("cell", (int, int, bool))

count = p.constraint("count", (int, int, int))
compute = p.constraint("compute", (int, int, int, int, bool, bool))


# Position
X = p.symbol("X")
Y = p.symbol("Y")
X1 = p.symbol("X1")
Y1 = p.symbol("Y1")
X2 = p.symbol("X2")
Y2 = p.symbol("Y2")

# Count
C = p.symbol("C")
C1 = p.symbol("C1")
C2 = p.symbol("C2")


# State
S1 = p.symbol("S1")
S2 = p.symbol("S2")
S = p.symbol("S")

# ticks
tick_count = p.constraint("tick_count", (), lazy=False)
tick_rule = p.constraint("tick_rule", (), lazy=False)


# Count state
p.propagation([tick_count(), cell(X, Y, ANON)], body=count(X, Y, 0))

p.propagation(
    positive_head=[tick_count(), cell(X1, Y1, True), cell(X2, Y2, S2)],
    guard=((Inline("abs(X1-X2)") <= 1) & (Inline("abs(Y1-Y2)") <= 1)),
    body=[
        compute(X1, Y1, X2, Y2, True, S2),
    ],
)

p.simpagation(
    positive_head=tick_count(),
    negative_head=[
        compute(X1, Y1, X2, Y2, True, True),
        count(X1, Y1, C1),
        count(X2, Y2, C2),
    ],
    body=[count(X1, Y1, C1 + 1), count(X2, Y2, C2 + 1)],
)

p.simpagation(
    positive_head=tick_count(),
    negative_head=[
        compute(X1, Y1, X2, Y2, True, False),
        count(X2, Y2, C2),
    ],
    body=[count(X2, Y2, C2 + 1)],
)

p.simpagation(
    positive_head=tick_count(),
    negative_head=[
        compute(X1, Y1, X2, Y2, False, True),
        count(X1, Y1, C1),
    ],
    body=[count(X1, Y1, C1 + 1)],
)

p.simpagation(
    positive_head=tick_count(),
    negative_head=[
        compute(X1, Y1, X2, Y2, False, False),
    ],
)

p.simplification(negative_head=tick_count(), body=tick_rule())

p.simpagation(
    positive_head=tick_rule(),
    negative_head=[cell(X, Y, True), count(X, Y, C)],
    guard=(C <= 1) | (C > 3),
    body=cell(X, Y, False),
)

p.simpagation(
    positive_head=tick_rule(),
    negative_head=[cell(X, Y, True), count(X, Y, C)],
    guard=((C >= 2) | (C <= 3)),
    body=cell(X, Y, True),
)


p.simpagation(
    positive_head=tick_rule(),
    negative_head=[cell(X, Y, False), count(X, Y, 3)],
    body=cell(X, Y, True),
)

p.simpagation(
    positive_head=tick_rule(),
    negative_head=[cell(X, Y, False), count(X, Y, C)],
    guard=(C != 3),
    body=cell(X, Y, False),
)

p.simpagation(
    negative_head=tick_rule(),
)

print(p.compile())


figure = [
    (1, 0, True),
    (2, 1, True),
    (0, 2, True),
    (1, 2, True),
    (2, 2, True),
]

# figure = [
#     (1, 0, True),
#     (1, 1, True),
#     (1, 2, True),
# ]

for x in range(10):
    for y in range(10):
        state = False
        for gx, gy, s in figure:
            if x == gx and y == gy:
                state = s
                break
        cell.post(x, y, state)


for i in range(0, 7):
    show_grid(cell.get())
    tick_count.post()
    sleep(0.8)
