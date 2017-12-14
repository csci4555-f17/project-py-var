
def list(*args):
    return lambda: args


print(list(1, 3, 5)())
