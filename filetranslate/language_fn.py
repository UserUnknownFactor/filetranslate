import re
#from random import random
from hashlib import sha1

MIN_REPEATS_IN_SFX = 2
MIN_SFX_SENTENCES = 2
NON_SFX_LETTERS_DIV = 2

ENABLE_TRUECASE = False
try:
    #from truecase import get_true_case
    ENABLE_TRUECASE = False #True # change this to manually set the state
except ImportError:
    pass

ENABLE_SFX_TO_ROMAJI = False #experimental
try:
    import pykakasi
    ENABLE_SFX_TO_ROMAJI = False #True # change this to manually set the state
except ImportError:
    pass

ranges = [
  {"from": ord(u"\u3300"), "to": ord(u"\u33ff")},         # compatibility ideographs
  {"from": ord(u"\ufe30"), "to": ord(u"\ufe4f")},         # compatibility ideographs
  {"from": ord(u"\uf900"), "to": ord(u"\ufaff")},         # compatibility ideographs
  {"from": ord(u"\U0002F800"), "to": ord(u"\U0002fa1f")}, # compatibility ideographs
  {"from": ord(u"\u3040"), "to": ord(u"\u309f")},         # Japanese Hiragana
  {"from": ord(u"\u30a0"), "to": ord(u"\u30ff")},         # Japanese Katakana
  {"from": ord(u"\u2e80"), "to": ord(u"\u2eff")},         # cjk radicals supplement
  {"from": ord(u"\u4e00"), "to": ord(u"\u9fff")},
  {"from": ord(u"\u3400"), "to": ord(u"\u4dbf")},
  {"from": ord(u"\U00020000"), "to": ord(u"\U0002a6df")},
  {"from": ord(u"\U0002a700"), "to": ord(u"\U0002b73f")},
  {"from": ord(u"\U0002b740"), "to": ord(u"\U0002b81f")},
  {"from": ord(u"\U0002b820"), "to": ord(u"\U0002ceaf")}  # included as of Unicode 8.0
]

kana_jpn = """
あア かカ さサ たタ なナ はハ まマ やヤ らラ わワ
いイ きキ しシ ちチ にニ ひヒ みミ りリ ゐヰ
うウ くク すス つツ ぬヌ ふフ むム ゆユ るル
えエ けケ せセ てテ ねネ へヘ めメ れレ ゑヱ
おオ こコ そソ とト のノ ほホ もモ よヨ ろロ をヲ
んン
が ガ ざ ザ だ ダ ば バ ぱ パ か゚ カ゚
ぎ ギ じ ジ ぢ ヂ び ビ ぴ ピ き゚ キ゚
ぐ グ ず ズ づ ヅ ぶ ブ ぷ プ く゚ ク゚
げ ゲ ぜ ゼ で デ べ ベ ぺ ペ け゚ ケ゚
ご ゴ ぞ ゾ ど ド ぼ ボ ぽ ポ こ゚ コ゚
きゃ しゃ ちゃ にゃ ひゃ みゃ りゃ
きゅ しゅ ちゅ にゅ ひゅ みゅ りゅ
きょ しょ ちょ にょ ひょ みょ りょ
ぎゃ じゃ びゃ ぴゃ き゚ゃ
ぎゅ じゅ びゅ ぴゅ き゚ゅ
ぎょ じょ びょ ぴょ き゚ょ
""".replace(' ','').replace('\n','')

ALL_JPN_RE= re.compile(r'[\u3041-\u3096]|[\u30A0-\u30FF]|[\u3400-\u4DB5\u4E00-\u9FCB\uF900-\uFA6A]|[\u2E80-\u2FD5]|[\uFF5F-\uFF9F]|[\u3000-\u303F]|[\u31F0-\u31FF\u3220-\u3243\u3280-\u337F]|[\uFF01-\uFF5E]|[\u2026-\u203B]', re.U)
SPACE_JP = '\u3000'
KANA_SFX = "あぁ うぅ おぉ いぃ えぇ ぶっ".replace(' ','')
PUNCTUATION_RE = re.compile(r'([\.!?])')
PUNCTUATION_EN = ".,!?;:"
PUNCTUATION_JP = SPACE_JP + "、 … 。 ？ ！ ～ \n".replace(' ','') #、
OTHER_JP = "ﾉｼジュ"
KANA_SFX_RE = re.compile(r'\b[%s%s]+\b' % (KANA_SFX, PUNCTUATION_JP), re.U)
FULLWIDTH_TO_NORMAL = str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ１２３４５６７８９０。、：！', 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890.,:!')

def unreplace_tags(text, tags_list, lang='JA'):
    fixed = text
    for line in tags_list:
        orig = line[0]
        tag = line[1]
        fixed = fixed.replace(tag, orig)
        if lang == 'JA':
            tag = tag.translate(FULLWIDTH_TO_NORMAL)
        fixed = fixed.replace(tag, orig)
        fixed = fixed.replace((tag[0].upper() + tag[1:]), orig)
        fixed = fixed.replace(tag.upper(), orig)
        fixed = fixed.replace(tag.lower(), orig)
        if len(orig) > 2 and (tag[-1:] in PUNCTUATION_EN):
            #sometimes MTLs gulp-down punctuation
            fixed = fixed.replace(tag[:-1], orig)
            fixed = fixed.replace(tag.upper()[:-1], orig)
            fixed = fixed.replace(tag.lower()[:-1], orig)
    return fixed
        
def tag_hash(string, str_enc="utf-8", hash_len=7, use_digits=False, lang='JA'):
    """ Generates short English tags for MTL from any kind of string.
    """
    if len(string) < 1: return ''
    d = sha1(string.encode(str_enc)).digest()
    s = ''
    n_chars = 26 + (10 if use_digits else 0)
    a_letter = ord('ａ' if lang == 'JA' else 'a')
    capA_letter = ord(chr(a_letter).upper())
    for i in range(0, hash_len):
        x = d[i] % n_chars
        if n_chars == 26:
            s += chr(a_letter + x) # lowercase letters, n_chars = 26
        elif n_chars == 26 + 10:
            if x >= 26:
                s += chr(a_letter - 49 + x - 26) # numbers, n_chars = 36
            else:
                s += chr(a_letter + x) # lowercase, n_chars = 36
        elif n_chars == 26 + 26: # unused since MTLs mess capitalization in JP->EN mode
            s += (chr(capA_letter + x - 26) if x >= 26 else chr(a_letter + x)) # all letters, n_chars = 52
        #else:
            #s += chr(int(random() * 26))

    endchar = '、' if lang == 'JA' else ','
    # indentation and endline checks
    if re.search(r"\A(?:\/\/)?(?:\t+|\A[\u0020\u3000]{2,})", string):
        endchar = '：' if lang == 'JA' else ':'
    elif re.search(r"\.\s*$", string):
        endchar = '！' if lang == 'JA' else '!'
    return s + endchar


def is_sfx(astring):
    """Checks if a string looks like SFX because of multiple repeating characters in a multiple sentences."""
    sfxes = KANA_SFX_RE.findall(astring)
    if not sfxes: return False
    all_letters = len(astring)
    non_sfx_letters = sum(letter.isalpha() for letter in astring if letter not in KANA_SFX and letter not in PUNCTUATION_JP)
    n_sfxes = len(sfxes)
    return n_sfxes >= MIN_SFX_SENTENCES and non_sfx_letters < all_letters / NON_SFX_LETTERS_DIV

"""
def make_romaji(astring, true_case=True):
    # Makes Romaji out of a Japanese text.
    kks = kakasi()
    if ENABLE_TRUECASE and true_case:
        return ' '.join([get_true_case(i["hepburn"]) for i in kks.convert(astring)])
    return ' '.join([i["hepburn"] for i in kks.convert(astring)])
"""

EN_LETTERS_RE = re.compile('[a-zA-Z]', re.U)
EN_ALL_RE = re.compile('^[\na-zA-Z0-9.,!?;:\"\'-=+()*&%$#@ ]+', re.U)
def is_in_language(text: str, lang: str, check_all:bool = False) -> bool:
    """ Checks if string contains a text with the selected language."""
    if lang == "JA" or lang == "JA_ALL": # Japanese
        return ALL_JPN_RE.search(text) is not None
    elif lang == "EN" or lang == "EN_ALL": # English
        if check_all:
            return EN_ALL_RE.search(text) is not None
        else:
            return EN_LETTERS_RE.search(text) is not None
    elif not lang or "ANY" in lang or "SKIP" in lang:
        return True
    return False

def tokenize_japanese(text: str):
    # Makes Romaji out of a Japanese text.
    kks = pykakasi.kakasi()
    result = kks.convert(text)
    #all_words
    for item in result:
        item["orig"]

def chunk(seq: list, num: int):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out

def is_incomplete(text: str, lang: str = "JA"):
    if lang == "JA":
        if '、' in text[-1:]:
            return True
    return False

def split_n(text:str, p:int = 3):
    words = list(text.split())
    lw = len(words)
    nw = lw // p + (lw % p > 0)

    lines= []
    i = 0
    current = ''

    for word in words:
        if i % nw == 0:
            if i > 0:
                lines.append(current)
            current = word
        else:
            current += ' ' + word
        i += 1
    lines.append(current)
    return lines