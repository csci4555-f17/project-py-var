#!/usr/bin/env python3

import ast
import textwrap
from functools import partial

# import astor

import x86ir as x86
from uniqify import Uniqifier
from explicate import Explicator
from heapify import heapify_free_vars
from closureconv import convert_closures
from flatten import flatten
from alloc import allocate_memory
from remcf import remove_ctrl_flow
from optimize import remove_useless_moves
from defunctioning import wrap_function


def call_in_succession(*funcs):
    def func(*args):
        res = args
        for f in funcs:
            if not isinstance(res, tuple):
                res = res,
            res = f(*res)
        return res
    return func


def print_function(f):
    import astor

    print(f.name, f.args)
    print('    ' + astor.dump_tree(f.body))
    print()
    return f


def print_x86ir(x86ir):
    print(x86.dump(x86ir))
    return x86ir


def join_program(main, functions):
    return textwrap.dedent("""
        .globl {}
        {}
    """).lstrip().format(main, '\n\n'.join(
        ('\n'.join(map(str, f)) for f in functions))
    )


def modify_index(index, func):
    def modifier(*args):
        return tuple(func(a) if i == index else a for i, a in enumerate(args))
    return modifier


def modify_attr(name, func):
    def modifier(obj):
        setattr(obj, name, func(getattr(obj, name)))
        return obj
    return modifier


pycompile = call_in_succession(
    ast.parse,
    # partial(astor.dump_tree, indentation='  ')
    Uniqifier().visit,
    # astor.to_source,
    Explicator().visit,
    heapify_free_vars,
    convert_closures,
    modify_index(1, lambda funcs: [call_in_succession(
        # print_function,
        modify_attr('body', call_in_succession(
            partial(map, flatten),
            lambda lists: [s for stmts, _ in lists for s in stmts],
            lambda stmts: allocate_memory(stmts, f.args),
            modify_index(0, remove_ctrl_flow),
            modify_index(0, remove_useless_moves)
        )),
        wrap_function
    )(f) for f in funcs]),
    join_program
)

if __name__ == "__main__":

    import os
    from argparse import ArgumentParser

    parser = ArgumentParser(
        description="Compile a python file (.py) into x86 assembly (.s)"
    )
    parser.add_argument("pyfile", help="The file to compile.")
    parser.add_argument('-d', '--debug', action='store_true',
                        help="Whether to print debug info")
    parser.add_argument('--print-assembly', action='store_true',
                        help="Whether to output to console instead of a file")
    parser.add_argument('-o', '--output', help="The file to output.")

    args = parser.parse_args()

    with open(args.pyfile) as src:
        compiled = pycompile(src.read())

    if args.print_assembly:
        print(compiled)

    else:

        output = args.output or os.path.splitext(args.pyfile)[0] + '.s'

        with open(output, 'w') as outfile:
            outfile.write(str(compiled))
