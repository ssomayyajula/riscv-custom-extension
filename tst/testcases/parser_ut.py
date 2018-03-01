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

    def testExtendHeaderCopyOld(self):
        # insert a function (do not care if correctly added or not)
        # and check if old header was copied and stored correctly
        name = 'copyheader'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        # now the header file should have been copied
        # check in our folder if we have a file
        opch_old = self.opcheader + '_old'
        self.assertTrue(os.path.exists(opch_old))
        self.assertTrue(os.path.isfile(opch_old))

        # check contents of file
        with open(opch_old, 'r') as fh:
            content = fh.readlines()

        self.assertEqual(len(content), 3)
        self.assertEqual(
            content[0], '/* Automatically generated by parse-opcodes.  */\n')
        self.assertEqual(content[1], '#ifndef RISCV_ENCODING_H\n')
        self.assertEqual(content[2], '#define RISCV_ENCODING_H\n')

    def testExtendHeaderRestoreOldHeader(self):
        # try restoring of old header function
        name = 'restoreheader'
        filename = self.folderpath + name + '.cc'

        args = self.Args(filename, restore=True)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust

        opchold = self.opcheader + '_old'
        oldcontent = 'old_header'
        with open(opchold, 'w') as fh:
            fh.write(oldcontent)

        parser.restore_header()

        with open(self.opcheader, 'r') as fh:
            hcontent = fh.readlines()

        self.assertEqual(hcontent[0], oldcontent)
        self.assertEqual(hcontent[-1], oldcontent)

        for file in os.listdir(self.folderpath):
            self.assertNotEqual(file, opchold)
            self.assertNotEqual(file, self.opcheader_cust)

    def testExtendHeaderCreateCustomHeader(self):
        # check if the files was created
        # no necessarity to have the correct content
        # that is part of the extensions class
        name = 'createcustomheader'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        self.assertTrue(os.path.exists(self.opcheader_cust))
        self.assertTrue(os.path.isfile(self.opcheader_cust))

    def testExtendHeaderPatchRiscvOpcH(self):
        # check if the include statement was added correctly
        name = 'patchheader'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        with open(self.opcheader, 'r') as fh:
            hcontent = fh.readlines()

        self.assertEqual(len(hcontent), 4)
        self.assertEqual(hcontent[0], '#include "riscv-custom-opc.h"\n')

    def testExtendHeaderPatchRiscvOpcHMultiple(self):
        # purpose is to check if the include statement is only added once
        name = 'testHeader0'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        name = 'testHeader1'
        self.funct3 = 0x01
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser1 = Parser(args)
        parser1.opch = self.opcheader
        parser1.opch_cust = self.opcheader_cust
        parser1.parse_models()
        parser1.extend_header()

        with open(self.opcheader, 'r') as fh:
            content = fh.readlines()

        self.assertEqual(content[0], '#include "riscv-custom-opc.h"\n')
        self.assertNotEqual(content[1], '#include "riscv-custom-opc.h"\n')

    def testExtendHeaderReplacedDefines(self):
        # check if the right ifdefs are in the file
        name = 'repl'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opch = self.opcheader
        parser.opch_cust = self.opcheader_cust
        parser.parse_models()
        parser.extend_header()

        with open(self.opcheader_cust, 'r') as fh:
            content = fh.readlines()

        self.assertEqual(
            content[0], '/* Automatically generated by parse-opcodes.  */\n')
        self.assertEqual(content[1], '#ifndef RISCV_CUSTOM_ENCODING_H\n')
        self.assertEqual(content[2], '#define RISCV_CUSTOM_ENCODING_H\n')

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

        name = 'testHeader3'
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

    def testExtendSourceCopyOld(self):
        # insert a function (do not care if correctly added or not)
        # and check if old opc source was copied and stored correctly
        name = 'copysource'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opcc = self.opcsource
        parser.parse_models()
        parser.extend_source()

        # now the header file should have been copied
        # check in our folder if we have a file
        opcc_old = self.opcsource + '_old'
        self.assertTrue(os.path.exists(opcc_old))
        self.assertTrue(os.path.isfile(opcc_old))
        # check contents of file
        with open(opcc_old, 'r') as fh:
            content = fh.readlines()

        self.assertTrue(content[0], '{ test }')
        self.assertTrue(content[-1], '{ test }')

    def testExtendSourceRestoreOldSource(self):
        # try restoring of old header function
        name = 'restoresource'
        filename = self.folderpath + name + '.cc'

        args = self.Args(filename, restore=True)
        parser = Parser(args)
        parser.opcc = self.opcsource

        opccold = self.opcsource + '_old'
        oldcontent = 'old_source'
        with open(opccold, 'w') as fh:
            fh.write(oldcontent)

        parser.restore_source()

        with open(self.opcsource, 'r') as fh:
            ccontent = fh.readlines()

        self.assertEqual(ccontent[0], oldcontent)
        self.assertEqual(ccontent[-1], oldcontent)

        for file in os.listdir(self.folderpath):
            self.assertNotEqual(file, opccold)

    def testExtendSourceIType(self):
        name = 'itype'
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opcc = self.opcsource
        parser.parse_models()
        parser.extend_source()

        with open(self.opcsource, 'r') as fh:
            content = fh.readlines()

        self.assertEqual(len(content), 7)
        self.assertEqual(
            content[2],
            '{"itype",  "I",  "d,s,j", MATCH_ITYPE, MASK_ITYPE, match_opcode, 0 },\n')

    def testExtendSourceRType(self):
        name = 'rtype'
        self.ftype = 'R'
        funct7 = 0x7f
        filename = self.folderpath + name + '.cc'
        self.genModel(name, filename, funct7)

        args = self.Args(filename)
        parser = Parser(args)
        parser.opcc = self.opcsource
        parser.parse_models()
        parser.extend_source()

        with open(self.opcsource, 'r') as fh:
            content = fh.readlines()

        self.assertEqual(len(content), 7)
        self.assertEqual(
            content[2],
            '{"rtype",  "I",  "d,s,t", MATCH_RTYPE, MASK_RTYPE, match_opcode, 0 },\n')
