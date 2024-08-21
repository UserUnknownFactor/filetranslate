# -*- coding: utf-8 -*-
"""
sugoitranslate
~~~~~~~~~~~~~~

Translation using Sugoi fairseq model.
To start working put or mklink `sugoi_v4model_fairseq`
directory into this file's one.

From
    /Sugoi_Toolkit_VX.0/Sugoi_Translator_Toolkit_VX/Code/backendServer/Program-Backend/Sugoi-Japanese-Translator/offlineTranslation/fairseq/
you will need to take `japaneseModel` and `spmModels`
and put them like this:

filetranslate/
    sugoi_v4model_fairseq/
        spm/
            spm.en.nopretok.model
            spm.en.nopretok.vocab
            spm.ja.nopretok.model
            spm.ja.nopretok.vocab
        big.pretrain.pt
        dict.en.txt
        dict.ja.txt
        LICENSE
        ...
"""
__version__ = '0.0.1'

import os, re
from fairseq.models.transformer import TransformerModel

class TranslationError(Exception):
    def __init__(self, message):
        super().__init__(message)

DEBUG = False

NON_CHARACTERS_RE = re.compile(r'^[^\w_]+$', re.UNICODE)
MULTIPLE_LINEFEEDS_RE = re.compile(r'\n+')


class SugoiTranslate():
    def __init__(self, src='JA', dest='EN', by_line=False,
                 model_path=f"{os.path.dirname(__file__)}\\sugoi_v4model_fairseq"):
        """ Sugoi translator init

        NOTE: It doesn't support other languages so don't init it with anything else.
        """
        self.source_lang = src.lower()
        self.target_lang = dest.lower()

        self.max_chars = 1500
        self.by_line = by_line
        self.inputModelPathOnly = model_path
        self.inputModelNameWithoutPath = 'big.pretrain.pt'
        self.device = 'cpu'
        self.bpe = 'sentencepiece'

        sentencePieceModelFolder0 = 'spm'
        sentencePieceModelPrefix = 'spm.'
        sentencePieceModelPostfix = '.nopretok.model'

        spFileName=f'{sentencePieceModelFolder0}{os.sep}{sentencePieceModelPrefix}{self.source_lang}{sentencePieceModelPostfix}'
        self.sourceSentencePieceModel= f'{self.inputModelPathOnly}{os.sep}{spFileName}'

        self.no_repeat_ngram_size=3

    def __enter__(self, *args, **kwargs):
        self.translator = TransformerModel.from_pretrained(
            self.inputModelPathOnly,
            checkpoint_file=self.inputModelNameWithoutPath,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            bpe=self.bpe,
            sentencepiece_model=self.sourceSentencePieceModel,
            no_repeat_ngram_size=self.no_repeat_ngram_size
        )

    def __exit__(self, *args, **kwargs):
        pass

    def wait(self):
        pass

    def get_char_limit(self):
        return 65536

    def translate(self, text, *args, **kwargs):
        """ Translates a string.

        :param text: Your text.
        :param src: Two-letter source language code.
        :param dest: Two-letter destination language code.
        :return: {origin: str, text: str}
        """

        if text is None:
            raise TranslationError("Source text cannot be None.")
        elif text == '':
            return text
        elif len(text) > self.max_chars:
            raise TranslationError(f"Text length is {len(text)} but translation limit is {self.max_chars}.")
            
        text = text.replace('\u2014', '\u30FC') #  BUG: — -> ー

        res_text_all = ''
        if self.by_line:
            one_time_cache = dict()
            lines = text.splitlines()
            for line in lines:
                text = line.strip()
                # fix sequences that baffle the neuronet
                text = text.replace('\u3000', ' ')
                text = re.compile(r'[…]+\s*$').sub('。', text) # ……$ -> 。$
                text = re.compile(r'[…]+\s*').sub('… ', text) # "……" -> "…<space>"
                text = re.compile(r' ?[\u0000-\u0006]').sub('', text)
                if text and text in one_time_cache:
                    res_text_all += one_time_cache[text] + '\n'
                else:
                    res = self.translator.translate(text).strip().replace('\n', ' ')
                    aibrainglitches = [
                        ("? ?", '?'),
                        ("! !", '!'),
                        ("? !", '?!'),
                        ("! ?", '!?'),
                    ]
                    for bg, bgr in aibrainglitches:
                        res = res.replace(bg, bgr)
                    res = re.sub(r"(.)\1{10,}", '', res) # repetitive sub-sentences
                    if DEBUG: print(text, "->", res)
                    if text and res:
                        one_time_cache[text] = res
                    res_text_all += res + '\n'

        else: # not by line
            # '…' char and utterances baffle the model somehow so it's better to preprocess them
            text = re.compile('…+').sub('… ', text)
            # Long spaces are long but outputted as is
            text = text.replace('\u3000', ' ')

            for dict_line in self.replacedict:
                if len(dict_line) < 1: continue
                replacer = '' if (dict_line[1] == None) else dict_line[1]
                text = re.sub(dict_line[0], replacer, text, flags=re.U)#|re.I|re.M)

            res_text_all = self.translator.translate(text)

        return res_text_all
