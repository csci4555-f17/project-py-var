
def list(*args):
    return lambda: args


lst = list(1, 3, 5)
i = 0
while i < len(lst()):
    print(lst()[i])
    i = i + 1
