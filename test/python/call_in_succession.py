
def call_in_succession(*funcs):
    def func(arg, f, *rest):
        return funcs(f(arg), rest) if len(rest) > 0 else arg
    return lambda arg: func(arg, funcs)


print(call_in_succession(
    lambda i: i + 1,
    lambda i: i + 2,
    lambda i: i + 3
)(1))
