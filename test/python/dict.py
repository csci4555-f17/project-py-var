
print({})

b = {
    1: 12,
    3: False,
    2091: (15 + 12 + 7)
}
print(b[1])
print(b[3])
print(b[2091])

b[4] = b[2091]
print(b[1])
print(b[3])
print(b[4])
print(b[2091])
