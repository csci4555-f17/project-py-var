
def list(*args):
    return args


i = 0
lst = list(1, 2, 3)
while i < len(lst):
    print(lst[i])
    i = i + 1
