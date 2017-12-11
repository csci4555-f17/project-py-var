
import ast

# free vares from course notes
# Functionally correct but have to update for our AST


def free_vars(n):
    if isinstance(n, Const):
        return set([])
    elif isinstance(n, Name):
        if n.name == 'True' or n.name == 'False':
            return set([])
        else:
            return set([n.name])
    elif isinstance(n, Add):
        return free_vars(n.left) | free_vars(n.right)
    elif isinstance(n, CallFunc):
        fv_args = [free_vars(e) for e in n.args]
        free_in_args = reduce(lambda a, b: a | b, fv_args, set([]))
        return free_vars(n.node) | free_in_args
    elif isinstance(n, Lambda):
        return free_vars(n.code) - set(n.argnames)


def heapify(node):
    fname = 'heapify_{}'.format(node.__class__.__name__)
    func = globals.get(fname, heapify_error)
    vars_to_heapify = free_vars(node)
    return func(node, vars_to_heapify)


def heapify_error(node):
    context = ""
    if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
        context = "@({}:{})".format(node.lineno, node.col_offset)
    detail = ast.dump(node) if isinstance(node, ast.AST) else str(node)
    raise NotImplementedError("could not heapify {}{}: {}".format(
        node.__class__, context, detail
    ))
