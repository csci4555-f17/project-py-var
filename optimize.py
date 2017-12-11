
from x86ir import Mov


def remove_useless_moves(statements):
    return [s for s in statements if not is_useless_move(s)]


def is_useless_move(stmt):
    return isinstance(stmt, Mov) and stmt.args[0] == stmt.args[1]
