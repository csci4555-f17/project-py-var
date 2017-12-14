
def print_all(arg, *rest):
    print(arg)
    return print_all(*rest) if rest else 0


print_all(1, [1, 2, 3], 14, 42)
