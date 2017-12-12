
def sum(n, *rest):
    return n + (sum(*rest) if rest else 0)
