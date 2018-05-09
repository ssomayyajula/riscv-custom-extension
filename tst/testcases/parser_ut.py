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

import os
import shutil
import sys
import unittest

from scripts import model_gen
from scripts.ccmodel import CCModel
from mako.template import Template

sys.path.append('..')
from modelparsing.exceptions import ConsistencyError
from modelparsing.parser import Parser
from tst import folderpath
sys.path.remove('..')


class TestParser(unittest.TestCase):
    '''
    Tests for the Parser class.
    More or less a complete functional test.
    '''

    class Args:
        '''
        Represent args, that parser needs.
        '''

        def __init__(self, modelpath, restore=False):
            self._modelpath = modelpath
            self._restore = restore

        @property
        def modelpath(self):
            return self._modelpath

        @property
        def restore(self):
            return self._restore

    def __init__(self, *args, **kwargs):
        super(TestParser, self).__init__(*args, **kwargs)
        # create temp folder
        if not os.path.isdir(folderpath):
            os.mkdir(folderpath)
        # test specific folder in temp folder
        test = self._testMethodName + '/'
        self.folderpath = os.path.join(folderpath, test)
        if not os.path.isdir(self.folderpath):
            os.mkdir(self.folderpath)

    def __del__(self):
        if os.path.isdir(folderpath) and not os.listdir(folderpath):
            try:
                os.rmdir(folderpath)
            except OSError:
                pass

    def setUp(self):
        # frequently used variables
        self.ftype = 'I'
        self.inttype = 'uint32_t'
        self.opc = 0x02
        self.funct3 = 0x00

        # prepare header and cc file
        self.opcheader = self.folderpath + 'opcheader.h'
        with open(self.opcheader, 'w') as fh:
            fh.write(
                '/* Automatically generated by parse-opcodes.  */\n' +
                '#ifndef RISCV_ENCODING_H\n' +
                '#define RISCV_ENCODING_H\n')
        self.opcheader_cust = self.folderpath + 'opcheadercust.h'
        self.opcsource = self.folderpath + 'opcsource.c'
        with open(self.opcsource, 'w') as fh:
            fh.write('{\n' +
                     '{ test },\n' +
                     '\n' +
                     '/* Terminate the list.  */\n' +
                     '{0, 0, 0, 0, 0, 0, 0}\n' +
                     '};')

    def tearDown(self):
        # remove generated file
        if hasattr(self, '_outcome'):  # Python 3.4+
            # these 2 methods have no side effects
            result = self.defaultTestResult()
            self._feedErrorsToResult(result, self._outcome.errors)
        else:
            # Python 3.2 - 3.3 or 3.0 - 3.1 and 2.7
            result = getattr(self, '_outcomeForDoCleanups',
                             self._resultForDoCleanups)

        error = ''
        if result.errors and result.errors[-1][0] is self:
            error = result.errors[-1][1]

        failure = ''
        if result.failures and result.failures[-1][0] is self:
            failure = result.failures[-1][1]

        if not error and not failure:
            shutil.rmtree(self.folderpath)

    def genModel(self, name, filename, funct7=0xff, faults=[]):
        '''
        Create local cc Model and from that cc file.
        '''
        self.ccmodel = CCModel(name,
                               self.ftype,
                               self.inttype,
                               self.opc,
                               self.funct3,
                               funct7,
                               faults)

        # generate .cc models
        modelgen = Template(filename=model_gen)

        with open(filename, 'w') as fh:
            fh.write(modelgen.render(model=self.ccmodel))

    def testExtendHeaderSingle(self):
        # extend the header with a single model
        name = 'singleHeader'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        with open(self.opcheader_cust, 'r') as fh:
            hcontent = fh.readlines()

        # first match then mask
        self.assertTrue(parser.instructions[0].match in hcontent)
        self.assertTrue(parser.instructions[0].mask in hcontent)
        self.assertTrue(parser.instructions[-1].match in hcontent)
        self.assertTrue(parser.instructions[-1].mask in hcontent)

    def testExtendHeaderMultiple(self):
        # extend the header with multiple models
        name = 'testHeader0'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        name = 'testHeader1'
        self.funct3 = 0x01
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        name = 'testHeader2'
        self.opc = 0x0a
        self.funct3 = 0x00
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        name = 'testHeader'
        self.funct3 = 0x01
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(self.folderpath)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        with open(self.opcheader_cust, 'r') as fh:
            hcontent = fh.readlines()

        # basically check if all masks and matches where added
        # maybe extend the test a little? don't know
        for inst in parser.instructions:
            self.assertTrue(inst.match in hcontent)
            self.assertTrue(inst.mask in hcontent)

    def testExtendHeaderSameMaskDifferentMatch(self):
        # try to generate two functions with different match but same mask
        # both should appear in header
        # how do we do that? try different func3
        name = 'func1'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        name = 'func2'
        filename = self.folderpath + name + '.cc'
        self.funct3 += 1
        self.genModel(name, filename)

        args = self.Args(self.folderpath)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        with open(self.opcheader_cust, 'r') as fh:
            hcontent = fh.readlines()

        self.assertTrue(parser.instructions[0].match in hcontent)
        self.assertTrue(parser.instructions[0].mask in hcontent)
        self.assertTrue(parser.instructions[-1].match in hcontent)
        self.assertTrue(parser.instructions[-1].mask in hcontent)
        self.assertTrue(parser.instructions[1].match in hcontent)
        self.assertTrue(parser.instructions[1].mask in hcontent)
        self.assertTrue(parser.instructions[-2].match in hcontent)
        self.assertTrue(parser.instructions[-2].mask in hcontent)

        self.assertEqual(len(parser.instructions), 2)

    def testExtendHeaderTwoTimesSingleModel(self):
        # add two models, both should appear in header file
        name = 'func1'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser1 = Parser(args)
        parser1.opch = self.opcheader
        parser1.opch_cust = self.opcheader_cust
        parser1.parse_models()
        parser1.extend_header()

        name = 'func2'
        filename = self.folderpath + name + '.cc'
        self.funct3 += 1
        self.genModel(name, filename)

        args = self.Args(filename)
        parser2 = Parser(args)
        parser2.opch = self.opcheader
        parser2.opch_cust = self.opcheader_cust
        parser2.parse_models()
        parser2.extend_header()

        with open(self.opcheader_cust, 'r') as fh:
            hcontent = fh.readlines()

        self.assertTrue(parser1.instructions[0].match in hcontent)
        self.assertTrue(parser1.instructions[-1].match in hcontent)
        self.assertTrue(parser1.instructions[0].mask in hcontent)
        self.assertTrue(parser1.instructions[-1].mask in hcontent)
        self.assertTrue(parser2.instructions[0].match in hcontent)
        self.assertTrue(parser2.instructions[-1].match in hcontent)
        self.assertTrue(parser2.instructions[0].mask in hcontent)
        self.assertTrue(parser2.instructions[-1].mask in hcontent)
