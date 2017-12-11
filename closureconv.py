
import ast
import extendedast as ext


def convert_closures(node):
    fname = 'convert_{}'.format(node.__class__.__name__)
    func = globals().get(fname, convert_default)
    return func(node)  # the rest just get passed through


def convert_Module(module):
    return _blockify(module, 'main')


def convert_Lambda(lba):
    return _blockify(lba, _new_function())


def convert_FunctionDef(func):
    return convert_closures(ast.copy_location(ast.Assign(
        [ast.Name(func.name, ast.Store())],
        ast.copy_location(ast.Lambda(func.args, func.body), func)
    ), func))


def convert_default(node):
    functions = []
    for field, child in ast.iter_fields(node):
        if isinstance(child, ast.AST):
            new_child, funcs = convert_closures(child)
            setattr(node, field, new_child)
            functions += funcs
        elif isinstance(child, list):
            for i, li in enumerate(child):
                child[i], funcs = convert_closures(child[i])
                functions += funcs
    return node, functions


def _blockify(node, name):
    node, blocks = convert_default(node)
    node.body = _tag_returns(node.body, name)
    args = getattr(node, 'args', None)
    args = [] if not args else [a.arg for a in args.args]
    return (
        ext.Closure(name),
        [ast.copy_location(ext.Function(name, args, node.body), node)] + blocks
    )


def _tag_returns(node, name):
    if isinstance(node, ast.Return):
        return ast.copy_location(ext.Return(node.value, name), node)
    elif isinstance(node, ast.AST):
        for field, n in ast.iter_fields(node):
            setattr(node, field, _tag_returns(n, name))
    elif isinstance(node, list):
        for i, n in enumerate(node):
            node[i] = _tag_returns(n, name)
    return node


def _new_function():
    _new_function.ctr += 1
    return 'lambda_{}'.format(_new_function.ctr)


_new_function.ctr = 0
