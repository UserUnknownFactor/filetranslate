# -*- coding:utf-8 -*-
import unittest, os, re, datetime, tempfile, copy
from filetranslate import *
from language_fn import *
from service_fn import *
#import tracemalloc
#tracemalloc.start()

class TestServiceFunctions(unittest.TestCase):

    indexed_array = [
                [0, 2, '[stag1] str1 etag1\nstag2 str2 etag2', [['[stag1] ', 'str1', ' etag1'], [ 'stag2 ', 'str2', ' etag2']], '[stag1] tran_str1 etag1\nstag2 tran_str2 etag2\n', None],
                [1, 1, 'stag3 str3', [['stag3 ', 'str3', None]], 'stag3 tran_str3', 'context' ],
                #etc.
            ]
    tags_array = [['[stag1]', 'repl_stag1'], ['etag1', 'repl_etag1'], ['stag2', 'repl_stag2'],
                  ['etag2', 'repl_etag2'], ['stag3', 'repl_stag3']]

    def test_is_cjk_substring(self):
        self.assertTrue(is_in_language('愛知県の県庁所在地で test test test', "JA_ALL"))
        self.assertFalse(is_in_language('test test test', "JA_ALL"))

    def test_is_sfx(self):
        self.assertFalse(is_sfx('愛知県の県庁所在地で'))
        self.assertTrue(is_sfx('あぁ... うぅ...'))

    def test_separate_tags_and_sentence(self):
        self.assertEqual(separate_tags_and_sentence(
            '[stag1] str1 etag2', TestServiceFunctions.tags_array),
            [ '[stag1] ', 'str1', ' etag2'])


    def test_string_from_indexed_array_item(self):
        self.assertEqual(
            string_from_indexed_array_item(TestServiceFunctions.indexed_array[0]),
            'str1\nstr2')

        self.assertEqual(
            string_from_indexed_array_item(TestServiceFunctions.indexed_array[1], True),
            'stag3 str3')

    def test_revert_text_to_indexed_array(self):
        copy0 = copy.deepcopy(TestServiceFunctions.indexed_array)
        copy1 = copy.deepcopy(TestServiceFunctions.indexed_array)

        copy0[0][3][0][1] = 'tran_str1'
        copy0[0][3][1][1] = 'tran_str2'
        self.assertEqual(
            revert_text_to_indexed_array('tran_str1\ntran_str2'.splitlines(), copy1, original_indexes=[0]),
            copy0
        )

        copy0[1][3][0][1] = 'tran_str3'
        self.assertEqual(
            revert_text_to_indexed_array('tran_str1\ntran_str2\ntran_str3'.splitlines(), copy1),
            copy0
        )

    def test_split_text_to_array(self):
        self.assertEqual(
            split_reader_to_array([['[stag1] str1 etag1\nstag2 str2 etag2', '[stag1] tran_str1 etag1\nstag2 tran_str2 etag2\n', None],
                                   ['stag3 str3', 'stag3 tran_str3','context']],
                                TestServiceFunctions.tags_array),
            TestServiceFunctions.indexed_array
        )

    def test_string_unescape(self):
        self.assertEqual(string_unescape('aaa\u0032bbbb'), 'aaa2bbbb')

    def test_num_groups(self):
        self.assertEqual(num_groups(re.compile('(aaa(bb)(.))(ccc)')), 4)


"""
    def test_split(self):
        s = 'hello world'
        self.assertEqual(s.split(), ['hello', 'world'])
        self.assertTrue('FOO'.isupper())
        self.assertFalse('Foo'.isupper())
        self.assertEqual('foo'.upper(), 'FOO')
        with self.assertRaises(TypeError):
            s.split(2)
"""

if __name__ == '__main__':
    unittest.main()