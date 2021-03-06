import re

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
    #import pykakasi
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

SPACE_JP = '\u3000'
KANA_SFX = "あぁ うぅ おぉ いぃ えぇ ぶっ".replace(' ','')
PUNCTUATION_JP = SPACE_JP + "、 … 。 ？ ！ ～".replace(' ','') #、
KANA_SFX_RE = re.compile(r'\b[%s%s]+\b' % (KANA_SFX, PUNCTUATION_JP), re.U)

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
def is_in_language(string, lang):
    """ Checks if string contains a text with the selected language."""
    if lang == "JA" or lang == "JA_ALL": # Japanese
        i = 0
        while i < len(string):
            # cjk ranges or punctuation characters
            if any([range["from"] <= ord(string[i]) <= range["to"] for range in ranges]) or (lang == "JA_ALL" and (string[i] in PUNCTUATION_JP)):
                return True
            i += 1
    elif lang == "EN" or lang == "EN_ALL": # English
        return EN_LETTERS_RE.search(string) is not None
    elif lang == "SKIP":
        return True
    return False

def tokenize_japanese(text):
    # Makes Romaji out of a Japanese text.
    kks = pykakasi.kakasi()
    result = kks.convert(text)
    #all_words
    for item in result:
        item['orig']

def chunk(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out

def is_incomplete(text, lang='JA'):
    if lang == 'JA':
        if '、' in text[-1:]:
            return True
    return False

def split_n(text, p=3):
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
            current += " " + word
        i += 1
    lines.append(current)
    return lines