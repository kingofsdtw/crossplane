#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys

from nginx_conf.parse import parse_file
from nginx_conf.errors import NgxParserBaseException

DELIMITERS = ('{', '}', ';')


def parse_args():
    from argparse import ArgumentParser

    # create parser and parse arguments
    parser = ArgumentParser(description='Formats an NGINX config file')
    parser.add_argument('filename', help='NGINX config file to format')
    parser.add_argument('-o', '--out', metavar='file', help='file to write to (default is stdout)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-i', '--indent', metavar='num', type=int, default=4, help='number of spaces to indent with')
    group.add_argument('-t', '--tabs', action='store_true', help='indent with tabs instead of spaces')
    args = parser.parse_args()

    # prepare filename argument
    args.filename = os.path.expanduser(args.filename)
    args.filename = os.path.abspath(args.filename)
    if not os.path.isfile(args.filename):
        parser.error('filename: No such file or directory')

    return args


def _escape(string):
    prev, char = '', ''
    for char in string:
        if prev == '\\' or prev + char == '${':
            prev += char
            yield prev
            continue
        if prev == '$':
            yield prev
        if char not in ('\\', '$'):
            yield char
        prev = char
    if char in ('\\', '$'):
        yield char


def needs_quotes(string):
    if string == '':
        return True
    elif string in DELIMITERS:
        return False

    # lexer should throw an error when variable expansion syntax
    # is messed up, but just wrap it in quotes for now I guess
    chars = _escape(string)

    # arguments can't start with variable expansion syntax
    char = next(chars)
    if char.isspace() or char in ('{', ';', '"', "'", '${'):
        return True

    expanding = False
    for char in chars:
        if char.isspace() or char in ('{', ';', '"', "'"):
            return True
        elif char == ('${' if expanding else '}'):
            return True
        elif char == ('}' if expanding else '${'):
            expanding = not expanding

    return char in ('\\', '$') or expanding


def enquote(arg):
    arg = str(arg.encode('utf-8'))
    if needs_quotes(arg):
        return repr(arg.decode('string_escape'))
    return arg


def _format(objs, padding, depth=0):
    margin = padding * depth

    for obj in objs:
        directive = obj['directive']
        args = [enquote(arg) for arg in obj['args']]

        if directive == 'if':
            line = 'if (' + ' '.join(args) + ')'
        elif args:
            line = directive + ' ' + ' '.join(args)
        else:
            line = directive

        if obj.get('block') is None:
            yield margin + line + ';'
        else:
            yield margin + line + ' {'
            for line in _format(obj['block'], padding, depth=depth+1):
                yield line
            yield margin + '}'


def format(filename, spaces=4):
    payload = parse_file(filename)
    if payload['status'] != 'ok':
        e = payload['errors'][0]
        raise NgxParserBaseException(e['error'], e['file'], e['line'])

    padding = '\t' if spaces is None else ' ' * spaces
    lines = _format(payload['config'][0]['parsed'], padding)
    output = '\n'.join(lines)

    return output


def main():
    args = parse_args()
    spaces = None if args.tabs else args.indent

    f = sys.stdout if args.out is None else open(args.out, 'w')
    try:
        f.write(format(args.filename, spaces) + '\n')
        f.flush()
    finally:
        if args.out is not None:
            f.close()


if __name__ == '__main__':
    main()

