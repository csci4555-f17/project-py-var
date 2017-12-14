
def sum(n, *rest):
    return n + (sum(*rest) if rest else 0)


print(sum(1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
