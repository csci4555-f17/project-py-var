
def get_list():
    return [1, 2, 3]


def print_all(x, *rest):
    print(x)
    return print_all(*rest) if len(rest) > 0 else 0


print_all(*get_list())
