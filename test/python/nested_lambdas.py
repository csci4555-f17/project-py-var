print((lambda a: (
    a + (lambda x: x + 1)(a)
))(5))
# print((lambda: lambda y: y + 1)()(4))
