def count_down(n):
    print(n)
    return 0 if n == 10 else count_down(n + 1)


print(count_down(3))
