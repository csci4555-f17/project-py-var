
def sum(w, x, y, z):
    print(w + x + y + z)


sum(1, 2, 3, 4)
sum(1, 2, *[3, 4])
sum(1, *[2, 3], 4)
sum(*[1, 2], 3, 4)
sum(*[1, 2], *[3, 4])
