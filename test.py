#!/usr/bin/env python3

import argparse
import unittest

import typing
if typing.TYPE_CHECKING:
    from typing import List, Optional


def argument_parser(prog_name: 'Optional[str]'=None):
    parser = argparse.ArgumentParser(prog_name)
    parser.add_argument(
        '-v', '--verbose',
        action='store_const', const=2, default=1, dest='verbosity',
        help='Verbose output; include test names and files'
    )
    parser.add_argument(
        '-q', '--quite',
        action='store_const', const=0, dest='verbosity',
        help='Minimal output; omit individual pass/fail messages'
    )
    parser.add_argument(
        '-b', '--buffer',
        action='store_true', default=False, dest='buffer',
        help='Buffer stdout and stderr during test runs'
    )
    parser.add_argument(
        '-f', '--failfast',
        action='store_true', default=False, dest='failfast',
        help='Stop testing on first failure'
    )
    parser.add_argument(
        '-s', '--start-directory',
        nargs=1, metavar='DIR', dest='start_dir',
        help='The starting directory for test discovery'
    )
    parser.add_argument(
        '-t', '--top-level-directory',
        nargs=1, metavar='DIR', dest='top_level',
        help='The top-level directory from which to import tests'
    )
    parser.add_argument(
        '-T', '--top-level-start',
        action='store_true', default=False, dest='top_level_share_start',
        help="Use the start directory as the top-level directory"
    )
    parser.add_argument(
        '-p', '--pattern',
        nargs=1, metavar='PATTERN', dest='pattern', default='test*.py',
        help="A glob-style pattern to match tests to run"
    )

    parser.add_argument(
        'tests',
        nargs='*',
        help="Individual test cases to run"
    )
    return parser


def run_discovery(runner: 'unittest.TextTestRunner', start_dir: str, pattern='test*.py',
                  top_level: 'Optional[str]'=None) -> None:
    test_loader = unittest.TestLoader()
    tests = test_loader.discover(start_dir, pattern, top_level)
    runner.run(tests)


def main(args: 'List[str]', pop_name: bool=True, default_start_dir="./tests/") -> int:
    program_name = "test.py"
    if pop_name:
        program_name = args.pop(0)

    arg_parser = argument_parser(program_name)

    options = arg_parser.parse_args(args)

    runner = unittest.TextTestRunner(verbosity=options.verbosity, failfast=options.failfast, buffer=options.buffer)
    if len(options.tests) == 0:
        start_dir = options.start_dir if options.start_dir is not None else default_start_dir
        top_level = options.top_level
        if options.top_level_share_start:
            if top_level is not None:
                print("May not specify -t and -T at same time")
                print(arg_parser.format_help())
                return 1
            top_level = options.start_dir

        tests = unittest.TestLoader().discover(start_dir, options.pattern, top_level)
        runner.run(tests)
    else:
        if options.start_dir is not None:
            print("May not specify start-directory and individual test cases at the same time")
            print(arg_parser.format_help())
            return 1
        if options.top_level is not None:
            print("May not specify top-level-directory and individual test cases at the same time")
            print(arg_parser.format_help())
            return 1
        if options.top_level_share_start:
            print("May not specify -T and individual test cases at the same time")
            print(arg_parser.format_help())
            return 1

        tests = unittest.TestLoader().loadTestsFromNames(options.tests)
        runner.run(tests)

    return 0


if __name__ == "__main__":
    import sys
    main(sys.argv)
