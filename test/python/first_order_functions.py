
def f(a):
    return lambda b: a + b


print(f(7)(4))
