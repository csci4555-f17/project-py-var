
import x86ir as x86


def remove_ifs(stmts):

    new_stmts = []
    for s in stmts:

        if not isinstance(s, x86.If):
            new_stmts.append(s)
            continue

        lbl_else, lbl_end = _free_jmp_labels()
        new_stmts += [
            x86.Cmp("$0", s.test),
            x86.Je(lbl_else)
        ]
        new_stmts += remove_ifs(s.body)
        new_stmts += [
            x86.Jmp(lbl_end),
            x86.Label(lbl_else)
        ]
        new_stmts += remove_ifs(s.orelse)
        new_stmts.append(x86.Label(lbl_end))

    return new_stmts


def _free_jmp_labels():
    _free_jmp_labels.ctr += 1
    suffix = '_label_{}'.format(_free_jmp_labels.ctr)
    return 'else' + suffix, 'end' + suffix


_free_jmp_labels.ctr = 0
