#!/usr/bin/env python

# Copyright (c) 2018 TU Dresden
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors: Robert Scheffel

import argparse
import ConfigParser
import logging
import logging.handlers
import os
import shutil
from modelparsing.parser import Parser

# get root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARN)

# # always write everything to the rotating log files
# if not os.path.exists('logs'):
#     os.mkdir('logs')
# log_file_handler = logging.handlers.TimedRotatingFileHandler(
#     'logs/args.log', when='M', interval=2)
# log_file_handler.setFormatter(logging.Formatter(
#     '%(asctime)s ' +
#     '[%(levelname)s]' +
#     '(%(name)s:%(funcName)s:%(lineno)d): %(message)s')
# )
# log_file_handler.setLevel(logging.DEBUG)
# root_logger.addHandler(log_file_handler)

# also log to the console at a level determined by the --verbose flag
console_handler = logging.StreamHandler()  # sys.stderr
# set later by set_log_level_from_verbose() in interactive sessions
console_handler.setLevel(logging.WARN)
console_handler.setFormatter(logging.Formatter(
    '[%(levelname)s](%(name)s): %(message)s'))
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)


class ModelParser():
    '''
    This class is used by the SConscript, to invoke the parser
    in build time
    '''

    def __init__(self):
        config = ConfigParser.ConfigParser()
        conffile = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '../config.ini')
        config.read(conffile)

        self.modelpath = os.path.expanduser(config.get("DEFAULT", "MODELPATH"))
        self.tcpath = os.path.expanduser(config.get("DEFAULT", "TOOLCHAIN"))

        assert(self.modelpath)
        assert(self.tcpath)

    def parse(self):
        modelparser = Parser(self.tcpath, self.modelpath)

        buildpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '../build')

        if not os.path.exists(buildpath):
            os.makedirs(buildpath)

        modelparser.parse_models()
        modelparser.extend_compiler()
        modelparser.extend_gem5()


def main():
    '''
    Main function.
    '''

    # argparsing
    parser = argparse.ArgumentParser(
        prog='modelparser',
        description='Parse reference implementations of custom extension ' +
        'models.')

    parser.add_argument('-b',
                        '--build',
                        action='store_true',
                        help='If set, the toolchain and Gem5 will be ' +
                        'rebuild.')
    parser.add_argument('-m',
                        '--modelpath',
                        type=str,
                        default=os.path.join(
                            os.path.dirname(__file__),
                            '../extensions'),
                        help='Path to model definition. ' +
                        'Can be a folder or a single file.')
    parser.add_argument('-r',
                        '--restore',
                        action='store_true',
                        help='If set, the toolchain will be restored ' +
                        'to its default.')
    parser.add_argument('-t',
                        '--toolchain',
                        default=os.path.abspath(
                            '/root/riscv-gnu-toolchain'))
    parser.add_argument('--tc-only',
                        action='store_true',
                        help='If set, only the toolchain is extended.')
    parser.add_argument('--gem5-only',
                        action='store_true',
                        help='If set, only gem5 is extended')
    parser.add_argument('-v',
                        '--verbose',
                        default=3,
                        action='count',
                        help='Increase output verbosity.')

    args = parser.parse_args()
    set_log_level_from_verbose(args)

    logger.info('Start parsing models')
    modelparser = Parser(args.toolchain, args.modelpath)

    buildpath = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '../build')

    if args.restore:
        if os.path.exists(buildpath):
            try:
                logger.info('Remove build directory')
                shutil.rmtree(buildpath)
            except OSError as e:
                logger.error("Error: %s - %s" % (e.filename, e.strerror))
        modelparser.restore()
    else:
        if not os.path.exists(buildpath):
            os.makedirs(buildpath)

        modelparser.parse_models()

        if not args.gem5_only:
            # extend compiler with models
            modelparser.extend_compiler()
        if not args.tc_only:
            # extend gem5
            modelparser.extend_gem5()

    # modelparser.remove_models()


def set_log_level_from_verbose(args):
    if not args.verbose:
        console_handler.setLevel('ERROR')
    elif args.verbose == 1:
        console_handler.setLevel('WARNING')
    elif args.verbose == 2:
        console_handler.setLevel('INFO')
    elif args.verbose >= 3:
        console_handler.setLevel('DEBUG')
    else:
        logger.critical("UNEXPLAINED NEGATIVE COUNT!")


if __name__ == '__main__':
    main()
