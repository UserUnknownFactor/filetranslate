﻿# -*- coding: utf-8 -*-
# The project requires Python 3.7 at the least

import os, sys
# add curent file's directory to path to include modules from the same folder
sys.path.append(os.path.dirname(__file__))

import re, argparse, textwrap, html, hashlib, datetime
import itertools, functools, pathlib, fnmatch
from shutil import copyfile, move
from time import sleep
from PIL import Image
from maxcolor import MaxColor
from language_fn import *
from service_fn import *

#from multiprocessing import Process

ENABLE_PROFILER = False
if ENABLE_PROFILER:
    import cProfile
    def profile_func(origin_func, *args, **kwargs):
        with cProfile.Profile() as prof:
            ret = prof.runcall(origin_func, *args, **kwargs)
            prof.print_stats()
            return ret
else:
    def profile_func(origin_func, *args, **kwargs):
        return origin_func(*args, **kwargs)


MAX_BORDER_TAGS = 4
MIN_INFILE_INTERSECTIONS = 2
MIN_LENGTH = 1 # minimum text length of all strings in a translation file
COMMENT_TAG = "//"

ENABLE_CACHE = False
cache = None
CACHE_EXPIRY_TIME = 3*24*60*60
TRANSLATION_BAN_DELAY = 30 * 60
CACHE_MIN_TEXT_LENGTH = 2

USE_GIT = False
GIT_AUTHOR = None

import hashlib
md5 = hashlib.md5
try:
    from diskcache import Cache
    ENABLE_CACHE = True # change this to manually set the state
except ImportError:
    pass

from ocrspace import OCRspace as OCRservice

MODULE_NAME = "filetranslate"
try:
    import git
    from git import RemoteProgress
    GIT_AUTHOR = git.Actor(MODULE_NAME, "noreply@example.com")
    USE_GIT = True # change this to manually set the state
except:
    pass

from pkg_resources import get_distribution
VERSION_STR = datetime.datetime.fromtimestamp(1600708851).strftime("%y.%m")
if get_distribution(MODULE_NAME):
    VERSION_STR = get_distribution(MODULE_NAME).version

CUT_CHARACTER = '✂' #\u2702
PROGRESS_CHAR = '•' #\u2022
PROGRESS_OTHER_CHAR = '→' #\u2192
TAB_REPLACER = '√' #\u221A
NEWLINE_REPLACER = '∞' # \u221E
SPACE_CHAR = ' ' #\u0020

REPLACEMENT_TAG_DB = "replacement_tags.csv"
TRANSLATION_IN_DB = "translation_dictionary_in.csv"
TRANSLATION_OUT_DB = "translation_dictionary_out.csv"
GAME_REGEXP_DB = "game_regexps.csv"
INTERSECTIONS_FILE = "intersections.csv"
DICTIOANRY_FILE = "dictionary.csv"
DEFAULT_OUT_DIR = "translation_out"
PROJECT_EXT = ".project"
GIT_INCLUDE_FILES = ["*.csv", "*.project", "*.svg"]
EXLUDED_DIRS = set([".git",".vscode",".backup", "__pycache__", "[Originals]", DEFAULT_OUT_DIR])

# processing RegExps
PUNCTUATION_OTHER = ' "\t\u0020\u3000/\\'
PUNCTUATION_OTHER_RE='[' + PUNCTUATION_OTHER + ']*'
PUNCTUATION_JPN_START = '«‘“｛〈《「' #［『【
PUNCTUATION_JPN_START_RE='[' + PUNCTUATION_OTHER + PUNCTUATION_JPN_START + ']*'
PUNCTUATION_JPN_END = '｝〉》」’”ー' #］』】
PUNCTUATION_JPN_END_RE='[' + PUNCTUATION_OTHER + PUNCTUATION_JPN_END + ']*'
PUNCTUATION_RE = re.compile(r'([\.!?])')
PUNCTUATION_EN = ".,!?;:"

TEXT_RE_SPLITTER = '|<===>|'
UNICODE_ESCAPE_RE = r'\\u[A-Fa-f\d]{4}'

STRINGS_NAME = "strings"
ATTRIBUTES_NAME = "attributes"
STRINGS_DB_POSTFIX = "_" + STRINGS_NAME + ".csv"
ATTRIBUTES_DB_POSTFIX = "_" + ATTRIBUTES_NAME + ".csv"

def tag_hash(string, str_enc="utf-8", hash_len=7):
    """ Generates short English tags for MTL from any kind of string.
    """
    if len(string) < 1: return ''
    d = hashlib.sha1(string.encode(str_enc)).digest()
    s = ''
    n_chars = 26 + 10
    for i in range(0, hash_len):
        x = d[i] % n_chars
        #s += chr(ord('a') + x) # lowercase letters, n_chars = 26
        s += (chr(ord('0') + x - 26) if x >= 26 else chr(ord('a') + x)) # numbers + lowercase, n_chars = 36
        #s += (chr(ord('A') + x - 26) if x >= 26 else chr(ord('a') + x)) # letters, n_chars = 52

    endchar = ','
    # indentation and endline checks
    if re.search(r"\A(?:\/\/)?(?:\t+|\A[\u0020\u3000]{2,})", string):
        endchar = ':'
    elif re.search(r"\.\s*$", string):
        endchar = '!'
    return s + endchar

def get_primary_color(pa, x1, x2, y1, y2):
    pixels = []
    for x in range(x1, x2):
        for y in range(y1, y2):
            try:
                if len(pa[x, y]) == 3:
                    pixels.append(pa[x, y]+(255,))
                else:
                    pixels.append(pa[x, y])
            except:
                continue
    return MaxColor(pixels).get_color(quality=1, no_white=False, no_black=False)


def make_array_from_nth_item_and_previous(n, value=None, prev_array=[]):
    assert n > 0, "Position should be non-zero."

    if not prev_array: prev_array = []
    l_old = len(prev_array)
    n_new = n
    n_new = max(n_new, l_old)

    ret = [None] * n_new
    ret[n-1] = value

    ret = [(prev_array[i] if (i < l_old and prev_array[i]) else item) for i, item in enumerate(ret)]
    return ret


def separate_tags_and_sentence(sentence, tags=[], unescape=False):
    starttag = ''
    endtag = ''

    # we search for up to 3 tags in any sequence at the string borders and move them to the array items
    all_tags = '(?:(?:' + '|'.join(re.escape(i[0]) for i in tags) + ')[ \u3000]*)+'
    for _ in range(MAX_BORDER_TAGS):
        # tags are strings, not regexps, so we escape them
        starttag_r = re.compile('^'+ PUNCTUATION_JPN_START_RE + all_tags + PUNCTUATION_JPN_START_RE).search(sentence)
        if starttag_r:
            starttag = starttag + starttag_r[0]
            sentence = sentence.replace(starttag_r[0], '')
            continue

        endtag_r = re.compile(PUNCTUATION_JPN_END_RE + all_tags + PUNCTUATION_JPN_END_RE + '$').search(sentence)
        if endtag_r:
            endtag = endtag_r[0] + endtag
            sentence = sentence.replace(endtag_r[0], '')
            continue

        if unescape:
            for i in tags:
                sentence = sentence.replace(i[0], string_unescape(i[1]))
        else:
            for i in tags:
                sentence = sentence.replace(i[0], i[1])

    if starttag == '': starttag = None
    if endtag == '': endtag = None

    if ENABLE_SFX_TO_ROMAJI and is_sfx(sentence):
        sentence = re.compile("[ゅっ]").sub('h', sentence).replace('……', '… ')
        #sentence = make_romaji(sentence)

    return [starttag, sentence, endtag]


def split_reader_to_array(reader_array, tags=[]):
    indexed_array = []
    i = 0
    for line in reader_array:
        arr = line[0].splitlines()
        l = len(arr) # for easier debugging
        for j, a in enumerate(arr):
            arr[j] = separate_tags_and_sentence(a, tags)

        indexed_array.append([i, l, line[0], arr] + line[1:])
        # indexed_array addressing format is thus
        # [item_n][0=index, 1=length, 2=orignial_line, 3=str_arr, 4=translation]([1=string, 0=stag, 2=etag] if str_arr)
        i += 1
    return indexed_array


def string_from_indexed_array_item(indexed_array_item, to_original=False):
    if to_original:
        if len(indexed_array_item[3]) == 1:
            return ''.join(filter(None, indexed_array_item[3][0]))
        return '\n'.join(''.join(filter(None, i)) for i in indexed_array_item[3]) + '\n' # we capture full lines so the last line should be \n terminated too
    return '\n'.join(i[1].strip() for i in indexed_array_item[3] if i[1] is not None)


def revert_text_to_indexed_array(translations_arr, indexed_array, **kwargs):
    """Moves translated text to indexed_array's items' [3][k][1] (main text element of each string) with overwrite.
    """
    original_indexes = kwargs.get("original_indexes", [])

    partial_l = len(original_indexes)
    translations_l = len(translations_arr)

    is_partial = (partial_l > 0)
    original_l = sum(i[1] for i in indexed_array if (not is_partial or (i[0] in original_indexes)))

    if translations_l != original_l:
        raise Exception(f"ERROR: number of translations ({translations_l}) doesn't match originals ({original_l})!")

    i = 0
    for row in indexed_array:
        j = row[0]
        if is_partial and j not in original_indexes: continue
        lines_originally = row[1]
        tmp = translations_arr[i:i+lines_originally]
        skip = False
        for k in range(lines_originally):
            if indexed_array[j][3][k][1] is None or len(indexed_array[j][3][k][1]) == 0: continue
            cur_tmp = tmp[k].strip()
            if len(cur_tmp) > 0:
                indexed_array[j][3][k][1] = cur_tmp
            else:
                skip = True # skip indexed_array items with falied translaions for future retry
                break

        i += lines_originally
        indexed_array[j][4] = '' if skip else string_from_indexed_array_item(indexed_array[j], True)

    return indexed_array


def write_svg(image, boxes, texts):
    """ Creates translation-ready SVG file from an image, bounding boxes and their text.
    """
    img = Image.open(image)
    width, height = img.size
    pixels = img.load() # this is not a list, nor it is list'able

    _, image_file = os.path.split(image)
    svg_text = """<svg xmlns="http://www.w3.org/2000/svg"
                xmlns:xlink="http://www.w3.org/1999/xlink"
                space="preserve"
                width="{width}"
                height="{heigth}"
                viewBox="0 0 {width} {heigth}">
                <defs/>
                <image xlink:href="{image}" x="0" y="0" height="{heigth}" title="{title}" width="{width}"/>
            """.format(width=width, heigth=height, image=image_file, title=image)
    svg_text = textwrap.dedent(svg_text)

    for i, rect in enumerate(boxes):
        x, y, w, h = rect
        pcolor = get_primary_color(pixels, x, x+h, y, y+w)
        svg_text += """
        <rect transform="translate({x}, {y})" fill="{color}" width="{width}" height="{heigth}"></rect>
        """.format(x=x, y=y, color=MaxColor.pix_to_hex(pcolor),  width=w, heigth=h)
        svg_text += """<text transform="translate({x}, {y})" fill="{color}" font-size="{heigth}" font-stretch="normal"
            kerning="0" letter-spacing="0" word-spacing="0"><tspan x="0">{text}</tspan></text>
        """.format(x=x, y=y+h, color=MaxColor.pix_to_hex(MaxColor.complement_pix(pcolor)),
                   heigth=h, text=re.sub(r'[<>\'\"]', '', texts[i]))
    svg_text = textwrap.dedent(svg_text)

    svg_text += "</svg>"
    with open(os.path.splitext(image)[0] + ".svg", "w", encoding="utf-8") as f:
        f.write(svg_text)

    return True

# skip files with no translatable strings found and already translated files
def translateCSV(self, trn_svc, file_name, type_str=True, upgrade=False):
    """ Translates or upgrades translations in database file with game texts.
    """
    j = 0
    if os.path.isfile(file_name):
        no_translations = False
        untl_lines = []
        with open(file_name, 'r', newline='', encoding=CSV_ENCODING) as f:
            untl_lines = [len(line) > 1 and len(line[1]) == 0 for line in csv.reader(f, DIALECT_TRANSLATION)]
        if not all(untl_lines) and not upgrade:
            return False
        if not any(untl_lines) and upgrade:
            return False

        max_chars = trn_svc.get_char_limit()
        string_tags = read_csv_list(os.path.join(self.work_dir, REPLACEMENT_TAG_DB))
        tr_dict_in = read_csv_list(os.path.join(self.work_dir, TRANSLATION_IN_DB))
        upgraded_lines = []
        is_translated = False

        with open(file_name, mode="r", encoding=CSV_ENCODING) as f:
            reader_ind = None
            print_progress(0, 100)
            if ENABLE_CACHE:
                cache = Cache("__pycache__")
                reader_ind = cache.get(file_name)
            if reader_ind is None:
                #print(TAB_REPLACER, end='', flush=True)
                reader_ind = split_reader_to_array(csv.reader(f, DIALECT_TRANSLATION), string_tags)
                if ENABLE_CACHE:
                    cache.set(file_name, reader_ind, expire=CACHE_EXPIRY_TIME)

            num_lines = sum(1 for row in reader_ind if row[4] is None or len(row[4]) == 0) if upgrade else len(reader_ind)
            progress_divisor = max(1, num_lines // 1000)
            print_progress(1, 100, type_of_progress=4)
            to_transl = []
            translated = []
            last_size = 0
            changed_lines = 0
            ttype = 0
            for row in reader_ind:
                if len(row[2]) == 0:
                    raise Exception("ERROR: no source text for item", changed_lines)
                if upgrade and row[4] is not None and len(row[4]) > 0: continue #have translation

                i = row[0]
                repl_line = string_from_indexed_array_item(reader_ind[i])
                if upgrade: upgraded_lines.append(i)

                # apply pre-translations from dictionary [jpn] -> [jpn; eng]
                for dict_line in tr_dict_in:
                    if len(dict_line) < 1: continue
                    replacer = '' if (dict_line[1] == None) else dict_line[1]
                    repl_line = re.sub(dict_line[0], replacer, repl_line, flags=re.U)#|re.I|re.M)

                # NOTE: Additional replacements should be done in a translation service class
                # or with translation_in. Batch translation in parts below max_chars:
                repl_line_len = len(repl_line)
                is_last = (changed_lines >= (num_lines - 1))
                # is_over_limit => new size + last size + linebreaks
                is_over_limit = last_size + repl_line_len + len(to_transl) * 1 >= max_chars
                if is_over_limit or is_last:
                    if is_last:
                        if is_over_limit:
                            ttype, _text = trn_svc.translate(to_transl, type_str and not upgrade)
                            translated += _text
                            to_transl = [repl_line]
                        else:
                            to_transl.append(repl_line)
                            last_size += repl_line_len
                    ttype, _text =  trn_svc.translate(to_transl, type_str and not upgrade)
                    translated += _text
                    to_transl = [repl_line]
                    last_size = repl_line_len
                else:
                    to_transl.append(repl_line)
                    last_size += repl_line_len

                changed_lines += 1
                if changed_lines % progress_divisor == 0:
                    print_progress(changed_lines, num_lines, type_of_progress=((1 if type_str else 2) if ttype > 0 else 3), start_from=2, end_with=98)

        # NOTE: translation should be checked for proper line count in the MT class or its override
        if not len(translated):
            print_progress(100, 100)
            return False
        reader_ind = revert_text_to_indexed_array(translated, reader_ind, original_indexes=upgraded_lines)

        with open(file_name, 'w', newline='', encoding=CSV_ENCODING) as f:
            writer = csv.writer(f, DIALECT_TRANSLATION)
            for row in reader_ind:
                i = row[0]
                writer.writerow([reader_ind[i][2], reader_ind[i][4]] + reader_ind[i][5:])

        print_progress(100, 100)

    return True


def process_image(ocr_svc, file_name):
    """ Creates OCR texts database file from a game image.
    """
    onlyName = os.path.splitext(file_name)[0]
    ocr_strings_fn = onlyName + STRINGS_DB_POSTFIX
    if os.path.isfile(onlyName + ".svg") or os.path.isfile(ocr_strings_fn):
        return False

    ocr_boxes, ocr_lines = ocr_svc.ocr(file_name)
    if len(ocr_lines):
        write_svg(file_name, ocr_boxes, ocr_lines)
        print("%d %s" % (len(ocr_lines), "OCR strings."), end='')
        try:
            with open(ocr_strings_fn, 'w', newline='', encoding=CSV_ENCODING) as f:
                writer = csv.writer(f, DIALECT_TRANSLATION)
                for line in ocr_lines:
                    writer.writerow([line, ''])
        except:
            print("ERROR: Cann't access file for writing:", ocr_strings_fn)
            return False
    else:
        return False
    return True


def strip_attr_matching_file(file_name, all_file_names):
    """ Comments attribute if there is a matching file in the game directory.
    """
    has_changes = False
    if os.path.isfile(file_name):
        with open(file_name, 'r', newline='', encoding=CSV_ENCODING) as f:
            reader = csv.reader(f, DIALECT_TRANSLATION)
            new_lines = []
            for line in reader:
                try:
                    attr = line[0].strip()
                    if attr and (attr in all_file_names):
                        new_lines.append([(COMMENT_TAG + line[0])]+line[1:])
                        if not has_changes:
                            print(": ", end='', flush=True)
                            has_changes = True
                        print(PROGRESS_CHAR, end='', flush=True)
                        continue
                except:
                    pass
                new_lines.append(line)

        if has_changes:
            write_csv_list(file_name, new_lines)

    return has_changes


def write_csv(file_name, str_list, is_string, upgrade=False, contexts=[]):
    """ Creates or upgrades corresponding translation database from an array of translations.
    """
    str_name = ''
    if is_string:
        str_name = STRINGS_NAME
    else:
        str_name = ATTRIBUTES_NAME
    if len(str_list) > 0:
        if not upgrade:
            print(" %d %s;" % (len(str_list), str_name), end='', flush=True)
        old_list = None
        old_name = file_name + "_" + str_name + ".old"
        if upgrade:
            old_list = read_csv_list(old_name)
            if len(old_list):
                print(" %d %s;" % (len(str_list), str_name), end='', flush=True)
        new_name = file_name + "_" + str_name + ".csv"
        if sum(len(n) for n in str_list) < MIN_LENGTH: return False
        #try:
        with open(new_name, 'w', newline='', encoding=CSV_ENCODING) as f:
            writer = csv.writer(f, DIALECT_TRANSLATION)
            have_contexts = (len(contexts) == len(str_list))

            """counts = dict()
            if upgrade and old_list:
                for old_line in old_list:
                    counts[old_line[0]] = counts.get(old_line[0], 0) + 1
            """

            for i, line in enumerate(str_list):
                trn = ''
                if upgrade and old_list:
                    for old_line in old_list:
                        if line == old_line[0]:
                            trn = old_line[1]
                            if is_string: old_list.remove(old_line)
                            break

                if have_contexts and is_string:
                    # TODO: set other translator columns after context for readability?
                    writer.writerow([line, trn, contexts[i]])
                else:
                    writer.writerow([line, trn])
        return True
        #except:
        #    print("ERROR: Cann't access file for writing: " + new_name)
    return False


def _makeTranslatableStrings(self, file_name, upgrade=False, lang="JA"):
    """ Creates or upgrades translation database from a game scenario file.
    """
    j = 0
    # don't duplicate attribute strings
    onlyName = os.path.splitext(file_name)[0]

    if upgrade:
        new_name = onlyName + ATTRIBUTES_DB_POSTFIX
        backup_attrs = onlyName + "_"+ ATTRIBUTES_NAME + ".old"
        if os.path.isfile(new_name) and not os.path.isfile(backup_attrs):
            move(new_name, backup_attrs)
        new_name = onlyName + STRINGS_DB_POSTFIX
        backup_strings = onlyName + "_" + STRINGS_NAME + ".old"
        if os.path.isfile(new_name) and not os.path.isfile(backup_strings):
            move(new_name, backup_strings)

    tags_fn = os.path.join(self.work_dir, REPLACEMENT_TAG_DB)
    old_string_tags = read_csv_dict(tags_fn)
    tr_dict_in = read_csv_dict(os.path.join(self.work_dir, TRANSLATION_IN_DB))

    attributes = dict()
    strings = []
    string_tags = dict()
    contexts = []
    with open(file_name, mode="r", encoding=self.file_enc) as f:
        content = f.read()

        # find attributes
        for match in self.re_a.finditer(content):
            # check if any of the groups matched
            match_groups = iter(a for a in match.groups() if a is not None)
            att_str = next(match_groups, None)
            while att_str is not None:
                if len(att_str) == 0:
                    att_str = next(match_groups, None)
                    continue
                if att_str and len(att_str)>0 and is_in_language(att_str, lang) and att_str not in attributes:
                    if self.re_t:
                        for tag in self.re_t.findall(att_str):
                            if (tag not in old_string_tags) and (tag not in string_tags) and (tag not in tr_dict_in):
                                string_tags[tag] = tag_hash(tag)
                    if self.re_a_sep:
                        sep_attrs = self.re_a_sep.findall(att_str)
                        if sep_attrs:
                            for sep_a in sep_attrs:
                                if len(sep_a) and not (self.re_excl and self.re_excl.search(sep_a)):
                                    attributes[sep_a] = ''
                        else:
                            if not (self.re_excl and self.re_excl.search(att_str)):
                                attributes[att_str] = ''
                    else:
                        if not (self.re_excl and self.re_excl.search(att_str)):
                            attributes[att_str] = ''
                    j += 1
                att_str = next(match_groups, None)

        # find strings
        for match in self.re_s.finditer(content):
            text_str = ''
            if self.has_text:
                text_str = match.group("text")
            else:
                text_str = match.group(1)

            if len(text_str) > 0 and is_in_language(text_str, lang):
                if self.re_t:
                    for tag in self.re_t.findall(text_str):
                        if (tag not in old_string_tags) and (tag not in string_tags) and (tag not in tr_dict_in):
                            string_tags[tag] = tag_hash(tag)

                if not (self.re_excl and self.re_excl.search(text_str)):
                    strings.append(text_str)

                    if self.has_context:
                        ctx = match.group("context")
                        contexts.append(ctx if ctx else '')
                    j += 1

    if len(attributes) == 0 and len(strings) == 0: return False
    write_csv(onlyName, attributes, False, upgrade)
    write_csv(onlyName, strings, True, upgrade, contexts)

    # check for tags that are in string_tags but not in tr_dict_in
    if len(string_tags) > 0:
        # remove all tr_dict_in tags from string_tags
        for tag in string_tags:
            if tag in tr_dict_in:
                del string_tags[tag]

        with open(tags_fn, 'w', newline='', encoding=CSV_ENCODING) as f:
            writer = csv.writer(f, DIALECT_TRANSLATION)
            # merge tags from previous files
            string_tags = list(merge_dicts(string_tags, old_string_tags).items())
            # sort tags by length and move tab&space tags first
            string_tags.sort(key=lambda l: (bool(re.search(r"\t| {2,}", l[0])), len(l[0])), reverse=True)
            for line in string_tags:
                # .,!: characters after tags should force MTLs to keep them in a proper position instead of rearranging
                writer.writerow(line)
    return (j > 0)


def prepare_csv_excel(file_name, restore=True):
    """ Converts translations to/from Excel-compatible spreadsheets by replacing
        tabulation and newline-inside-row characters.
    """
    if not os.path.exists(file_name): return False
    torigin = TAB_REPLACER if restore else '\t'
    treplacer = '\t'  if restore else TAB_REPLACER
    norigin = NEWLINE_REPLACER if restore else '\n'
    nreplacer = '\n'  if restore else NEWLINE_REPLACER
    old_list = read_csv_list(file_name, ftype=(DIALECT_EXCEL if restore else DIALECT_TRANSLATION))
    if not len(old_list): return

    for i, row in enumerate(old_list):
        if row[0]:
            old_list[i][0] = row[0].replace(torigin, treplacer)
            old_list[i][0] = row[0].replace(norigin, nreplacer)
        if len(row) > 1 and row[1]:
            old_list[i][1] = row[1].replace(torigin, treplacer)
            old_list[i][1] = row[1].replace(norigin, nreplacer)
        if len(row) > 2 and row[2]:
            old_list[i][2] = row[2].replace(torigin, treplacer)
            old_list[i][2] = row[2].replace(norigin, nreplacer)

    write_csv_list(file_name, old_list, ftype=(DIALECT_TRANSLATION if restore else DIALECT_EXCEL))
    return True

def _applyCutMarks(self, interval=40, cut_chrs=CUT_CHARACTER, mind_chr=SPACE_CHAR, use_bytelength=False, skip_processed=False):
    """ Cuts a string into interval-sized parts using `cut_chrs`.
        If `interval == 1`, original string's (byte-)length is used.
        The `cut_ch`r can be the engine's line separator or a unicode marker for manual processing.
        Can process strings based on their byte length in the provided encoding.
    """
    if not interval: return
    csv_files = list(find_files(self.work_dir, ['*' + STRINGS_DB_POSTFIX])) #, '*' + ATTRIBUTES_DB_POSTFIX
    for a_file in csv_files:
        #print(PROGRESS_CHAR, end='', flush=True)
        old_attrs = read_csv_list(a_file)
        old_attrs_len = len(old_attrs)
        print_progress(0, 100)
        for i, line in enumerate(old_attrs):
            if len(line) < 2: continue
            transl_line = line[1]
            j = 1

            if skip_processed and cut_chrs in transl_line: continue # skip already processed lines

            if interval > 1: # `interval = 1` is used for cutting to original line's length
                tmp_arr = []
                tmp_str = transl_line

                if cut_chrs in transl_line: # in that case we'll check only unprocessed last part
                    spl_str = transl_line.rsplit(cut_chrs, maxsplit=1)
                    tmp_arr.append(spl_str[0])
                    tmp_str = spl_str[1]

                if use_bytelength: # cut based on string byte-length, necessary for binary replacements
                    j = 0
                    while len(tmp_str) and j < len(tmp_str):
                        len_tmp = len(tmp_str[:j+1].encode(self.file_enc))
                        if len_tmp >= interval:
                            tmp_arr.append(tmp_str[:j])
                            tmp_str = tmp_str[j:]
                            j = 0
                        j += 1
                else:
                    tmp_str_len = len(tmp_str)
                    mnd_chr_len = len(mind_chr)
                    while tmp_str_len > interval:
                        where = interval
                        if (mind_chr is not None):
                            where_rspace = tmp_str[:interval].rfind(mind_chr)
                            if where_rspace < 2 or tmp_str[interval-1] in PUNCTUATION_EN:
                                where_rspace = interval
                            where = min(interval, where_rspace)
                            tmp = tmp_str[:where]
                            if tmp[:mnd_chr_len] == mind_chr:
                                tmp = tmp[mnd_chr_len:]
                            tmp_arr.append(tmp)
                            tmp_str = tmp_str[where:]
                            if tmp_str[:mnd_chr_len] == mind_chr:
                                tmp_str = tmp_str[mnd_chr_len:]
                        else:
                            tmp_arr.append(tmp_str[:where])
                            tmp_str = tmp_str[where:]
                        j += 1
                        tmp_str_len = len(tmp_str)
                if len(tmp_arr):
                    if len(tmp_str): tmp_arr.append(tmp_str) # add last part to array
                    transl_line = cut_chrs.join(tmp_arr)
            else:
                if use_bytelength:
                    tmp_arr = []
                    j = 0
                    interval = len(line[0].encode(self.file_enc))
                    while j < len(transl_line):
                        if len(transl_line[:j+1].encode(self.file_enc)) >= interval:
                            tmp_arr.append(transl_line[:j])
                            tmp_arr.append(transl_line[j:])
                            break
                        j += 1
                    if len(tmp_arr):
                        transl_line = cut_chrs.join(tmp_arr)
                else:
                    len_orig = len(line[0])
                    if len_orig > 1 and len(transl_line) > len_orig:
                        transl_line = transl_line[:len_orig] + cut_chrs + transl_line[len_orig:]
            old_attrs[i][1] = transl_line
            print_progress(i, old_attrs_len, end_with=98)

        write_csv_list(a_file, old_attrs)
        print_progress(100, 100)


def _applyIntersectionAttributes(self, check_type=1, csv_files=[]):
    intersecta = read_csv_list(os.path.join(self.work_dir, INTERSECTIONS_FILE))
    if len(csv_files) == 0:
        csv_files = list(find_files(self.work_dir, ['*' + ATTRIBUTES_DB_POSTFIX]))
        if check_type > 1: csv_files += list(find_files(self.work_dir, ['*' + STRINGS_DB_POSTFIX]))

    for a_file in csv_files:
        old_attrs = read_csv_list(a_file)
        is_changed = False
        for i, line in enumerate(old_attrs):
            index = None
            try:
                index = next((i for i, a in enumerate(intersecta) if line[0] == a[0]), None)
            except Exception as e:
                print("\nERROR: No original line in file", a_file)
                raise e
            if index is not None:
                old_attrs[i] = [line[0], intersecta[index][1]] + line[2:]
                is_changed = True

        if is_changed:
            print(PROGRESS_CHAR, end='', flush=True)
            write_csv_list(a_file, old_attrs)


def _intersectAttributes(self, check_type=1, csv_files=[]):
    if len(csv_files) == 0:
        csv_files = list(find_files(self.work_dir, ['*' + ATTRIBUTES_DB_POSTFIX]))
        if check_type > 1: csv_files += list(find_files(self.work_dir, ['*' + STRINGS_DB_POSTFIX]))
    attributes_sets = []
    attributes_lists = dict()
    single_file_repeats = set()

    # those are relatively small databases so we can safely load them all to memory
    for a_file in csv_files:
        attr_file_l = read_csv_list(a_file)
        all_attrs = [i[0] for i in attr_file_l if len(i) > 0 and i[0].strip()]
        attributes_sets.append(set(all_attrs))
        if check_type > 2:
            single_file_repeats |= set([i[0] for i in attr_file_l if len(i) > 0 and i[0].strip() and all_attrs.count(i[0]) >= MIN_INFILE_INTERSECTIONS])
        attributes_lists[a_file] = attr_file_l

    intrsec_all = []
    for a, b in itertools.combinations(attributes_sets, 2):
        c = a & b
        if len(c):
            intrsec_all.append(c)
    intrsec_all = set().union(*intrsec_all) | single_file_repeats

    old_intersections = read_csv_list(INTERSECTIONS_FILE)
    for iatr in intrsec_all:
            for i, atrs in enumerate(attributes_sets):
                is_break = False
                for atr in atrs:
                    if atr == iatr:
                        # attributes_files should have same indexes as attributes_sets
                        fnd = attributes_lists[csv_files[i]]
                        index = next((i for i, a in enumerate(fnd) if atr == a[0]), None)
                        if index is not None and not any(atr == a[0] for a in old_intersections):
                            old_intersections.append(fnd[index])
                        is_break = True
                        break
                if is_break: break

    old_intersections.sort(key=lambda l: l[0])
    write_csv_list(os.path.join(self.work_dir, INTERSECTIONS_FILE), old_intersections)

def _makeDictionary(self, check_type=2, csv_files=[]):
    dictionary = read_csv_list(os.path.join(self.work_dir, DICTIOANRY_FILE))
    if len(csv_files) == 0:
        csv_files = list(find_files(self.work_dir, ['*' + STRINGS_DB_POSTFIX]))
        if check_type > 1: csv_files += list(find_files(self.work_dir, ['*' + ATTRIBUTES_DB_POSTFIX]))

    import fugashi
    tagger = fugashi.Tagger()

    dictionary_set = set(i[0] for i in dictionary)
    old_dictionary_set = dictionary_set.copy()
    for a_file in csv_files:
        for txt in read_csv_list(a_file):
            words = set(word.surface for word in tagger(txt[0]))
            dictionary_set |= words

    new_dictionary = dictionary + [[str(word), ''] for word in dictionary_set if word not in old_dictionary_set]
    new_dictionary.sort(key=lambda l: l[0])
    dct_file = os.path.join(self.work_dir, DICTIOANRY_FILE)
    print("found", len(new_dictionary), "words.\nWriting dictionary as: " + dct_file)
    write_csv_list(dct_file, new_dictionary)

def _replaceInTranslations(self, a_file, old_re, new_repl, repl_file=None):
    """ Replaces by RegExp in translations.
    """
    is_changed = False
    a_file_l = read_csv_list(a_file)
    cnt = 0
    repl_file_l = None
    if repl_file:
        repl_file_l = read_csv_list(repl_file)
        if len(repl_file_l) > 0:
            for i, repl in enumerate(repl_file_l):
                repl_file_l[i][0] = re.compile(re.escape(repl[0]), re.M|re.U)
        else:
            repl_file_l = None

    for i, translation in enumerate(a_file_l):
        if len(translation) < 2 or not translation[1]: continue
        tmp = translation[1]
        if repl_file_l:
            for repl in repl_file_l:
                tmp = repl[0].sub(repl[1], tmp)
        else:
            tmp = old_re.sub(new_repl, tmp)
        if tmp != translation[1]:
            a_file_l[i][1] = tmp
            cnt += 1
            if not is_changed: is_changed = True
    if is_changed:
        write_csv_list(a_file, a_file_l)
    return cnt


def _applyFixesToTranslation(self, transl_fn, is_string=True):
    """ Applies translation fixes from replacement_tags and translation_dictionary_out
        to translation databases.
    """
    only_name = transl_fn
    if is_string:
        transl_fn += STRINGS_DB_POSTFIX
    else:
        transl_fn += ATTRIBUTES_DB_POSTFIX

    string_tags_dict = read_csv_list(os.path.join(self.work_dir, REPLACEMENT_TAG_DB))
    tr_dict_out = read_csv_list(os.path.join(self.work_dir, TRANSLATION_OUT_DB)) if is_string else []

    old_list = read_csv_list(transl_fn)
    len_old_list = len(old_list)
    progress_divisor = max(1, len_old_list // 100)
    if  len_old_list == 0: return False
    new_list = []
    is_fixed = False

    print_progress(0, 100)
    for i, row in enumerate(old_list):
        fixed = ''
        if len(row)>1 and row[1] is not None:
            fixed = row[1]
            for dict_line in string_tags_dict:
                fixed = fixed.replace(dict_line[1], dict_line[0])
                fixed = fixed.replace((dict_line[1][0].upper() + dict_line[1][1:]), dict_line[0])
                fixed = fixed.replace(dict_line[1].lower(), dict_line[0])
                if len(dict_line[0]) > 2 and (dict_line[1][-1:] in PUNCTUATION_EN):
                    #sometimes MTLs gulp-down punctuation
                    fixed = fixed.replace(dict_line[1][:-1], dict_line[0])

            # Apply fixes from translation_dictionary_out [eng] -> [eng fixed]
            #    We do it here, not right after translation, to  backup unfixed copy and
            #    see what machine-translator will do to tags in original strings
            for dict_line in tr_dict_out:
                if len(dict_line[0]) > 0:
                    fixed = re.sub(r'%s' % dict_line[0], r'%s' % dict_line[1], fixed, flags=re.M)

            if not is_fixed and fixed != row[1]: is_fixed = True
            if i % progress_divisor == 0:
                print_progress(i, len_old_list, end_with=98)

        new_list.append([row[0], fixed] + row[2:])

    # TODO: fix context from attributes
    if self.has_context and is_string:
        attr_dic = read_csv_list(only_name + ATTRIBUTES_DB_POSTFIX)
        if len(attr_dic) > 0:
            for row in new_list:
                if len(row) < 3: continue
                for attr in attr_dic:
                    match = re.search(re.escape(attr[0]), row[2])
                    if match:
                        row[2] = row[2].replace(match[0], attr[1])
                        if not is_fixed: is_fixed = True
    if is_fixed:
        write_csv_list(transl_fn, new_list)

    print_progress(100, 100)
    return is_fixed

def _applyTranslationsToFile(self, file_name, mode=1):
    """ Applies translations from translation databases to game files and images
        and places results in translation_out directory.
    """

    splitName = os.path.splitext(file_name)
    onlyName = splitName[0]
    onlyExt = splitName[1][1:]

    if not (os.path.exists(onlyName + STRINGS_DB_POSTFIX) or os.path.exists(onlyName + ATTRIBUTES_DB_POSTFIX)): return

    #try:
    #If we write to the same folder make a backup
    #if not os.path.exists(fileName + ".bak"):
    #    copyfile(fileName, fileName + ".bak")
    re_a = self.re_a
    re_s = self.re_s
    # to apply translations to .svg-s
    if self.img_exts:
        if onlyExt in self.img_exts:
            file_name = splitName[0] + ".svg"
            re_a = None
            re_s = re.compile(r'%s' % r'<tspan x="0">([^<]+)<', re.MULTILINE)

    outputName = ''
    useGameDir = (self.game_dir and self.game_dir != ''  and os.path.exists(self.game_dir))
    if useGameDir:
        # WARNING: backup game files before owerwriting
        outputName = file_name.replace(self.work_dir.rstrip(os.sep), self.game_dir.rstrip(os.sep))
        #print(f"Using game directory {outputName}...")
    else:
        outputName = file_name.replace(self.work_dir, os.path.join(self.work_dir, DEFAULT_OUT_DIR))
        #print(f"Writing to directory {outputName}...")
    # skip already translated files, delete them manually to redo
    if not os.path.exists(file_name) or (os.path.exists(outputName) and not (useGameDir or (mode & 2))):
        #print("skipped, already applied and not replacement mode or original missing", end='', flush=True)
        return False

    print_progress(0, 100)

    torg_text = u''
    with open(file_name, mode="r", encoding=self.file_enc) as torg:
        torg_text = torg.read()

    apply_txt = False
    #onlyName = onlyName.replace(workDir, workDir + "\\translations")
    forig_t_lines = 0
    err_flag = False

    str_fn = onlyName + STRINGS_DB_POSTFIX
    if os.path.exists(str_fn) and re_s:
        with open(str_fn, 'r', newline='', encoding=CSV_ENCODING) as f:
            reader = csv.reader(f, DIALECT_TRANSLATION)
            #re_endline = re.compile("[?!\"'.]|\.{2}")
            #last_line_continues = False

            split_torg_text = re_s.split(torg_text)

            len_split_torg_text = len(split_torg_text)
            progress_divisor = max(1, len_split_torg_text // 100)

            if self.has_text and self.context_gn > 1 and self.has_context and self.context_gn:
                gn = self.context_gn + 2
                split_torg_text = [a for i, a in enumerate(split_torg_text)
                                   if a is not None and (i != self.context_gn and (i+2) % gn != 0)]

            for row in reader:
                if self.strip_comments and row[0][:len(COMMENT_TAG)] == COMMENT_TAG: continue
                forig_t_lines += 1
                try:
                    tmp_str = row[1]
                    if not tmp_str: continue
                except:
                    if row[0] is None or len(row[0]) < 5:
                        err_flag = True
                    else:
                        print("Error on string line #", forig_t_lines, "text: \n", row[0])
                    continue
                if err_flag:
                    print("Error on previous string line #", forig_t_lines-1, "text: \n", row[1])
                    err_flag = False

                if self.escape_dquo_a:
                    tmp_str = tmp_str.replace('"', '\\"')

                # makes string true case, doesn't bode well with tags and macros
                #if ENABLE_TRUECASE and tc_enable:
                #    tmp_str = get_true_case(tmp_str)
                '''
                # if line continues over linebreak make first word lowercase
                # should ignore names and places with dictionary...
                if last_line_continues:
                    a = tmp_str.split(" ")
                    if (a[0] != "\"I" and a[0] != "I")
                    a[0] = a[0].lower()
                    tmp_str = a.join(" ")
                '''
                #torg_text = re.sub(re_s, tmp_str, torg_text, 1)
                #print(match)
                for i, orig_ln in enumerate(split_torg_text):
                    if orig_ln == '"' or orig_ln == "'": continue
                    if orig_ln == row[0]:
                        split_torg_text[i] = tmp_str
                        break
                #last_line_continues = (len(re.findall(re_endline, row[1][-3:])) > 0)
                if not apply_txt:
                    apply_txt = True

                if forig_t_lines % progress_divisor == 0:
                    print_progress(i, len_split_torg_text, end_with=70)

        if apply_txt:
            torg_text = ''.join(filter(None, split_torg_text))

    apply_att = False
    forig_a_lines = 0
    att_fn = onlyName + ATTRIBUTES_DB_POSTFIX
    if os.path.exists(att_fn) and re_a:
        alines = []
        with open(att_fn, 'r', newline='', encoding=CSV_ENCODING) as f:
            alines = list(csv.reader(f, DIALECT_TRANSLATION))

        #check for errors
        for row in alines:
            forig_a_lines += 1
            try:
                translated = row[1]
            except:
                if row[0] is None or len(row[0]) < 5:
                    err_flag = True
                else:
                    print("Error on attribute line #", forig_t_lines, "text: \n", row[0])
                continue
            if err_flag:
                print("Error on previous attribute line #", forig_t_lines-1, "text: \n", row[1])
                err_flag = False

        alines.sort(key=lambda l: len(l[0]), reverse=True)

        # quotes can be escaped manually with -rit command line parameter
        # TODO: cmdline opt to make first attribute letter uppercase and rest - lowercase

        def attr_block_replacer_fn(match):
            fixed_match = match[0]
            original_match = fixed_match
            found_groups = filter(lambda x: x[1] is not None, enumerate(match.groups(), start=1))

            i, found = next(found_groups, (0, None))
            if self.re_a_sep and self.re_a_sep.search(found):
                fixed_match = re.sub(self.re_a_sep, individual_attr_replacer_fn, fixed_match)
            else:
                text_spans = []
                current = 0
                start = match.start()
                first, last = match.span(i)
                first = first - start
                last = last - start
                '''if i == 0:
                    for row in alines:
                        if found == row[0]:
                            fixed_match = fixed_match.replace(found, row[1])
                    i, found = next(found_groups, (0, None))
                    continue'''
                while found is not None:
                    prefix = original_match[current:first]
                    if len(prefix): text_spans.append(prefix)
                    item = found
                    for row in alines:
                        if item == row[0]: item = row[1]
                    if len(item): text_spans.append(item)
                    i, found = next(found_groups, (0, None))
                    if i != 0:
                        n_first, n_last = match.span(i)
                        n_first = n_first - start
                        n_last = n_last - start
                        first = n_first
                    else:
                        n_last = last
                        first = len(original_match)
                    current = last
                    last = n_last

                text_spans.append(original_match[last:])
                fixed_match = ''.join(text_spans)
            return fixed_match

        def individual_attr_replacer_fn(match):
            attr_text = match.group(1)

            if not len(attr_text): return match[0]
            for row_inner in alines:
                if len(attr_text):
                    if attr_text == row_inner[0]:
                        return match[0].replace(attr_text, row_inner[1])
            return match[0]

        torg_text = re.sub(re_a, attr_block_replacer_fn, torg_text)
        if forig_a_lines: apply_att = True

    print_progress(90, 100)

    if apply_att and (mode & 4):
        out_dict = read_csv_list(os.path.join(self.work_dir, TRANSLATION_OUT_DB))
        for dict_line in out_dict:
            repl = re.compile(dict_line[0])
            torg_text = repl.sub(dict_line[1], torg_text)

    print_progress(95, 100)

    if (apply_txt or apply_att) and torg_text and len(torg_text) > MIN_LENGTH:
        pathOut = os.path.dirname(outputName)
        if pathOut != '' and not os.path.exists(pathOut):
            os.makedirs(pathOut, exist_ok=True)
        try:
            torg_text = torg_text.encode(self.file_enc)
        except UnicodeEncodeError as u:
            # pylint: disable=unsubscriptable-object
            print("Error converting unicode string", u.object[max(0, u.start-1):min(len(u.object), u.start+10)],
                  "to", self.file_enc)
            sys.exit(2)
        with open(outputName, mode="wb") as torg:
            torg.write(torg_text)

        print_progress(100, 100)
        return ((forig_t_lines + forig_a_lines) > 0)

    print_progress(100, 100)
    #except:
    #    print("ERROR: Cannot access file")
    #    return False
    return False


def is_git_repo(path):
    """Checks if provided path is a git repository."""
    try:
        _ = git.Repo(path).git_dir
        return True
    except:
        return False


def _createRepo(self):
    """Creates a git repository from project files in the working folder."""
    if is_git_repo(self.work_dir):
        #self._updateRepo("after reinitialization")
        return
    r = git.Repo.init(self.work_dir)
    r.index.add(list(find_files(self.work_dir, GIT_INCLUDE_FILES)))
    r.index.commit("Initial commit", author=GIT_AUTHOR, committer=GIT_AUTHOR)


class git_progress_print(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print("\r%10s %03d %3d %3f %20s" % (op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE"), end='', flush=True)

def _updateRepo(self, tag=None, add_new=False, to_origin=0, silent=True):
    """Updates project files in its git repository."""
    if not is_git_repo(self.work_dir): return
    r = git.Repo(self.work_dir)
    if not r.is_dirty():
        if to_origin == 2:
            origin = r.remote("origin")
            if not origin.exists():
                if self.remote_url:
                    origin = r.create_remote("origin", self.remote_url)
                else:
                    return
            if origin.exists():
                for checkout_info in origin.fetch(progress=git_progress_print()):
                    print("Updated %s to %s" % (checkout_info.ref, checkout_info.commit))
                print('')
        return

    #if tag:
    #    r.create_tag(tag)
    modified_files = [(item.change_type + ": " + item.a_path) for item in r.index.diff(None)]
    if len(modified_files) and not silent:
        print("  Modified files:\n   " + "\n   ".join(modified_files))

    #r.git.add(update=True)
    r.git.add(list(find_files(self.work_dir, GIT_INCLUDE_FILES)))
    msg = ' '.join(filter(None, ["Update", tag, datetime.datetime.now().strftime("%d.%m.%Y") ]))
    r.index.commit(msg, author=GIT_AUTHOR, committer=GIT_AUTHOR)
    if to_origin == 2:
        origin = r.remote("origin")
        if not origin.exists():
            if self.remote_url:
                origin = r.create_remote("origin", self.remote_url)
            else:
                return
        if origin.exists():
            origin.set_tracking_branch(origin.refs.master)
            origin.push()


def _revertRepo(self):
    if not is_git_repo(self.work_dir): return
    r = git.Repo(self.work_dir)
    if r.is_dirty():
        r.head.reset("HEAD", index=True, working_tree=True)
        print("HEAD commit (%s)..." % r.head.commit.message.strip())
    else:
        r.head.reset("HEAD~1", index=True, working_tree=True)
        print("previous commit (%s)..." % r.head.commit.message.strip())


def _archiveRepo(self, fn="filetranslate"):
    """Exports project's git repository to a zip archive."""
    if not is_git_repo(self.work_dir): return
    try:
        fn = os.path.split(os.path.split(self.work_dir + os.sep)[0])[1]
    except:
        pass
    self.updateRepo(tag="before archival")
    fn += ".zip"
    with open(os.path.join(self.work_dir, fn), "wb") as fp:
        git.Repo(self.work_dir).archive(fp, format="zip")
    return fn


class FileTranslate:
    """Game file translation tools.
    """
    def __init__(self, work_dir, img_exts, file_enc, re_a, re_s, re_t, re_a_sep, re_excl,
                 game_dir=None, git_origin='', c_gn=0,
                 has_t=False, has_ct=False, edquo=False, cap_a=False, strip_cmts=True):

        self.re_a = re.compile(r'%s' % re_a, re.MULTILINE)
        self.re_s = re.compile(r'%s' % re_s, re.MULTILINE)
        self.re_t = re.compile(r'%s' % re_t) if re_t else None
        self.re_a_sep = re.compile(r'%s' % re_a_sep) if re_a_sep else None
        self.re_excl = re.compile(r'%s' % re_excl) if re_excl else None

        self.has_text = False
        self.has_context = False
        self.context_gn = 0
        if self.re_s.groups > 1:
            try:
                #do we have a (?P<context>) group?
                self.context_gn = self.re_s.groupindex["context"]
                self.has_context = True
            except:
                pass
            try:
                #do we have a (?P<text>) group?
                self.re_s.groupindex["text"]
                self.has_text = True
            except:
                raise Exception("There should be (?P<text>) capture group in main text RegExp for more than 1 group")

        self.work_dir = work_dir.rstrip(os.sep)
        self.img_exts = img_exts
        self.file_enc = file_enc.strip()
        self.game_dir = game_dir.rstrip(os.sep) if game_dir else None
        self.escape_dquo_a = edquo
        self.cap_a = cap_a
        self.remote_url = git_origin
        self.strip_comments = strip_cmts

    translateCSV = translateCSV
    makeTranslatableStrings = _makeTranslatableStrings
    applyFixesToTranslation = _applyFixesToTranslation
    applyTranslationsToFile = _applyTranslationsToFile
    applyIntersectionAttributes = _applyIntersectionAttributes
    applyCutMarks = _applyCutMarks
    intersectAttributes = _intersectAttributes
    replaceInTranslations = _replaceInTranslations
    makeDictionary = _makeDictionary
    createRepo = _createRepo
    updateRepo = _updateRepo
    archiveRepo = _archiveRepo
    revertRepo = _revertRepo


def find_files(dir_path: str=None, patterns: [str]=None, exclude_files: [str]=None) -> [str]:
    """Returns a generator yielding files matching the given patterns.

    :type dir_path: str
    :type patterns: [str]
    :rtype : [str]
    :param dir_path: Directory to search for files/directories under. Defaults to current dir.
    :param patterns: Patterns of files to search for. Defaults to ["*"]. Example: ["*.json", "*.xml"]
    """
    path = dir_path or "."
    path_patterns = patterns or ["*"]
    path_patterns = list(set(map(os.path.basename, patterns)))
    dir_patterns = list(set(filter(lambda d: d != '', map(os.path.dirname, patterns))))
    if len(dir_patterns) == 0:
        dir_patterns = [path]

    exclude_dirs = EXLUDED_DIRS
    #exclude_files = [".7z",".zip",".old"]

    for d in dir_patterns:
        for root_dir, dir_names, file_names in os.walk(d):
            dir_names[:] = list(filter(lambda x: not x in exclude_dirs, dir_names))
            filter_partial = functools.partial(fnmatch.filter, file_names)

            for file_name in itertools.chain(*map(filter_partial, path_patterns)):
                if exclude_files and any(fnmatch.fnmatch(file_name, p) for p in exclude_files): continue
                yield os.path.join(root_dir, file_name)

def check_translation_types(original_lines, lang_src, is_seq_strings, not_translit_mode, need_merge):
    """ Makes array of string line translation types:
        -1: restore original line or assign empty,
        0: ignore line,
        1: one-liner,
        N >= 2: N-merged lines (including starting)
    """
    translation_types = []
    l_orig = len(original_lines)
    i = 0
    while i < l_orig:
        if original_lines[i].strip() == '' or (
            not is_in_language(original_lines[i], lang_src)) or (
            not_translit_mode and is_sfx(original_lines[i])):
            i += 1
            translation_types.append(-1)
            continue
        line_type = 1
        j = 0
        line = ''
        if need_merge:
            # in case the last string of the block is incomplete, ignore that
            prev_full = False
            while is_seq_strings and (i + j < l_orig):
                line += original_lines[i + j]
                if (i + j < l_orig - 1) and is_incomplete(original_lines[i + j], lang_src):
                    j += 1
                else:
                    break
        if j > 0:
            original_lines[i] = line
        lastj = j + 1
        translation_types.append(lastj)
        while j > 0:
            j -= 1
            translation_types.append(0)
        i += lastj

    return translation_types

def restore_translation_lines(original_lines, translated_lines, translation_types, not_translit_mode):
    """ Restores array of translated lines using translation types and actual translation results
    """
    translated_lines_all = []
    l_orig = len(original_lines)
    i = 0
    ti = 0
    while i < l_orig:
        if translation_types[i] == -1:
            skip_untranslatable = not_translit_mode# and is_sfx(l_orig_lines[i]))
            translated_lines_all.append('' if skip_untranslatable else original_lines[i])
            i += 1
            continue
        if ti > (l_orig - 1): # shoudn't be here
            breakpoint
            break
        j = 0
        if translation_types[i] > 1:
            if i == l_orig - 1: #shoudn't be here
                # just in case the last line is partial, merge all N parts into it
                breakpoint
                n = ti + translation_types[i]
                t = ''
                while ti < len(translated_lines):
                    t += (' ' + translated_lines[ti])
                    ti += 1
                    if ti > n: break
                translated_lines_all.append(t)
            else:
                translated_parts = split_n(translated_lines[ti], translation_types[i])
                n_split = len(translated_parts)
                if (n_split == translation_types[i]):
                    for part in translated_parts:
                        translated_lines_all.append(part)
                else: # translator returned too few words: unsplittable >_<
                    n_split = 0
                    while (n_split < translation_types[i]):
                        n_split += 1
                        translated_lines_all.append('')

            ti += 1
            j = translation_types[i]
        elif translation_types[i] == 1:
            translated_lines_all.append(translated_lines[ti])
            j = 1
            ti += 1
        else: #shoudn't be here
            breakpoint
            j = 1
            ti += 1
        i += j

    return translated_lines_all

def make_text_to_translate(source_lines, translation_types):
    """ Returns only lines that need to be translated according to translation_types
    """
    filtered_lines = ''
    l_orig = len(source_lines)
    for i, line in enumerate(source_lines):
        if translation_types[i] > 0:
            filtered_lines += line
            if i < l_orig - 1:
                filtered_lines += '\n'
    return filtered_lines

# ---------------------------------------------- plans -----------------------------------------------
# TODO:
# - [x] Exlude strings from adding to translation database by regexp in game_regexps.csv.
# - [ ] Support for translating raw binary blobs with {fileanme}_raw.csv (format: address=>original=>translation).
# - [ ] Option to apply string cutting only in -a mode.
# - [ ] Configuration to enable for string cutting as binary / keep byte-length (partailly done).
# - [ ] Translation from/to other languages maybe.
# - [x] Merge N following incomplete sentences to the first incomplete. Check by 、, Make 2 arrays before translation: length of split N + translatable strings T = > N=1 =  nosplit; N=2+ => reset and replace N-1 next strings with remainders from first split N times by nearest space; 0 => skip string translation

# ----------------------------------------------- main -----------------------------------------------
def main():
    working_dir = os.path.abspath(os.getcwd())
    game_engine = ''
    game_directory = None
    text_exts = ["txt", "json"]
    def_pat = ','.join("*." + i for i in text_exts)
    img_exts = ["png", "jpg", "jpeg", "webp"]

    # process .project file and read the game directory location if it's there
    for f in [f for f in os.listdir(working_dir) if os.path.isfile(f) and (
        os.path.splitext(f)[1] and os.path.splitext(f)[1] == PROJECT_EXT)]:
        game_engine = os.path.splitext(f)[0]
        with open(f, 'r', encoding="utf-8") as gf:
            game_directory = gf.readline()
            if game_directory == '': game_directory = None
        break

    # try working dir first then project dir for RegExp db
    regexp_db = os.path.join(working_dir, GAME_REGEXP_DB)
    if not os.path.isfile(regexp_db):
        regexp_db = os.path.join(os.path.dirname(os.path.realpath(__file__)), GAME_REGEXP_DB)

    project_types = []
    # for list of game engines supported
    if os.path.isfile(regexp_db):
        with open(regexp_db, 'r', newline='', encoding=CSV_ENCODING) as f:
            reader = csv.reader(f, DIALECT_TRANSLATION)
            for line in reader:
                project_types.append(line[0])
    project_types = ", ".join(project_types)

    parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=textwrap.dedent(f"""
         additional information and reminders:
            • current directory is: {working_dir}\\
            • current project type is: {game_engine}
            • initial translation step (-t) skips files with translated strings in corresponding .csv;
            • edit translation files, _attributes.csv and _strings.csv, not files from \\translation_out,
               to future-proof your project;
            • verify regular expressions' validity on actual game files;
            • command line parameters take priority over database entries;

         special databases (DSVs column-separated by {DELIMITER_CHAR} with quote character {ESCAPE_CHAR}):
           game_regexps.csv:
             DSV file with game-specific file encodings, extensions and regexp patterns;
           replacement_tags.csv:
             DSV file with tags found in strings. Replace comma with :.?! to help MTL position them.
             When preparing strings for MTL, translation_dictionary_in has priority.
           add or move permanent manual fixes to the following files:
               translation_dictionary_in.csv:
                 DSV file with replacements before translating text (jpn → eng or jpn → jpn);
               translation_dictionary_out.csv:
                 DSV file with replacements for -fix option (eng → eng);
         """))

    parser.add_argument("-e", help="Original encoding (ex: cp932, cp1252 etc; utf-8 by default)", default='', metavar=("encoding"))
    parser.add_argument("-p", help=f"File patterns (ex: {def_pat})", default='', metavar=("file_patterns"))
    parser.add_argument("-g", default=game_engine, help=f"Game engine preset ({project_types})", metavar=("game_engine"))
    parser.add_argument("-lang", default='JA-EN', help=f"Translaton direction pair SRC-DEST (ex: JA-EN)", metavar=("game_language"))
    #parser.add_argument("-d", help="Directory of the source files (current by default)", default=working_dir, metavar=("default_path"))
    parser.add_argument("-gd", default=game_directory, help="Directory of the original game files", metavar=("game_files_path"))
    parser.add_argument("-cm", default=CUT_CHARACTER, help="Cut-mark string or character", metavar=("cut_mark"))
    parser.add_argument("-nomerge", help="Don't merge partial sequental strings during translation", action="store_true")

    regroup = parser.add_argument_group("regexps")
    regroup.add_argument("-ra", help="RegExp for attributes", default='', metavar=("attr_regexp"))
    regroup.add_argument("-rs", help="RegExp for texts", default='', metavar=("text_regexp"))
    regroup.add_argument("-rt", help="RegExp for text tags", default='', metavar=("tag_regexp"))
    regroup.add_argument("-rex", help="RegExp for text exclusion", default='', metavar=("exc_regexp"))

    optgroup = parser.add_argument_group("stage").add_mutually_exclusive_group()
    optgroup.add_argument("-i", help="Inititalize translation files", action="store_true")
    optgroup.add_argument("-u", help="Update translation files for new strings", action="store_true")
    optgroup.add_argument("-ocr", help="Perform text recognition for images", action="store_true")
    optgroup.add_argument("-t", help="Perform initial string translation", type=int, nargs='?', const=1, default=0, metavar="N")
    optgroup.add_argument("-tu", help="Perform translation of new strings", type=int, nargs='?', const=1, default=0, metavar="N")
    optgroup.add_argument("-fix", help="Revert replacement tags and apply translation_dictionary_out to translation", action="store_true")
    optgroup.add_argument("-cut", help="Add cut-mark character after N-letters", type=int, nargs='?', const=1, default=0, metavar="N")
    optgroup.add_argument("-a", help="Apply translation to original files (dafault: 1: skip existing, 2:replace, 4:apply dictionary_out; can be sum)", type=int, nargs='?', const=1, default=0, metavar="mode")

    replgroup = parser.add_argument_group("replacement")
    replgroup.add_argument("-rit", help="Replace text in translations by RegExp (used with -f or both -o and -n options)", action="store_true")
    replgroup.add_argument("-o", help="RegExp for old text", default='', metavar=("old_regexp"))
    replgroup.add_argument("-n", help="New text RegExp replacer", default='', metavar=("new_replacer"))
    replgroup.add_argument("-f", help="Replacers DSV database (ex: replacers.csv)", default='', metavar=("replacers_file"))

    intsgroup = parser.add_argument_group("additional").add_mutually_exclusive_group()
    intsgroup.add_argument("-ca", help="Comment attributes with corresponding game file", action="store_true")
    intsgroup.add_argument("-isc", help="Create intersection of strings in files (1:attributes, 2:+strings, default: 3:+infile-duplicates)", type=int, nargs='?', const=3, default=0, metavar="type")
    intsgroup.add_argument("-isa", help="Apply intersection file to translations (1:attributes, default: 2:+strings)", type=int, nargs='?', const=2, default=0, metavar="type")
    intsgroup.add_argument("-dct", help="Make dictionary file from all original words (default: 1:strings 2:+attributes)", type=int, nargs='?', const=2, default=0, metavar="type")
    intsgroup.add_argument("-tdct", help="Translate dictionary file", type=int, nargs='?', const=1, default=0, metavar="N")
    intsgroup.add_argument("-tdctu", help="Update translation of dictionary file", type=int, nargs='?', const=1, default=0, metavar="N")

    if USE_GIT:
        # GIT related stuff
        gitgroup = parser.add_argument_group("git")
        gitgroup.add_argument("-url", default='', help="Git origin URL", metavar=("git_origin"))
        gitgroup = gitgroup.add_mutually_exclusive_group()
        gitgroup.add_argument("-commit", help="Commit changes to the repository (default: 1:local, 2:origin)", type=int, nargs='?', const=1, default=0, metavar="type")
        gitgroup.add_argument("-revert", help="Reverts ALL changes, if not commited, otherwise reverts to the previous commit", action="store_true")
        gitgroup.add_argument("-exp", help="Export git repository as a zip file", action="store_true")
        gitgroup.add_argument("-nogit", help="Disable Git usage", action="store_true")

    exgroup = parser.add_argument_group("excel").add_mutually_exclusive_group()
    exgroup.add_argument("-px", help="Prepare for Excel or OpenOffice (√ = tab, ∞ = newline)", action="store_true")
    exgroup.add_argument("-rx", help="Revert Excel or OpenOffice compatibility for -a and -fix options", action="store_true")

    if len(sys.argv) < 2:
        print("FileTranslate " + VERSION_STR)
        parser.print_help(sys.stderr)
        return
    app_args = parser.parse_args()

    patterns = list(filter(None, app_args.p.split(',')))
    is_pattern_manual = (len(patterns) > 0)
    file_encoding = app_args.e
    regexp_attr = app_args.ra
    regexp_txt = app_args.rs
    regexp_tag = app_args.rt
    regexp_excl = app_args.rex
    regexp_attr_sep = None
    lang_src, lang_dest = app_args.lang.split('-')

    if os.path.isfile(regexp_db):
        if app_args.g and len(app_args.g) > 0:
            with open(regexp_db, 'r', newline='', encoding=CSV_ENCODING) as f:
                reader = csv.reader(f, DIALECT_TRANSLATION)
                for line in reader:
                    if line[0] == app_args.g:
                        if not file_encoding: file_encoding = line[1]
                        if not is_pattern_manual: patterns = line[2].split(',')
                        ars = line[3].replace('\n', '').split(TEXT_RE_SPLITTER)
                        if not regexp_attr: regexp_attr = ars[0]
                        if not regexp_attr_sep: regexp_attr_sep = ars[1] if len(ars) > 1 else None
                        if not regexp_txt: regexp_txt = line[4].replace('\n', '')
                        if len(line) > 5 and not regexp_tag: regexp_tag = line[5].replace('\n', '')
                        if len(line) > 6 and not regexp_excl: regexp_excl = line[6].replace('\n', '')
                        break

    if len(patterns) == 0:
        patterns = list("*." + i for i in text_exts)
    image_patterns = list("*." + i for i in img_exts)

    if app_args.g and len(app_args.g) > 0:
        print("Game engine: " + app_args.g)
    if app_args.gd and len(app_args.gd) > 0:
        if not os.path.exists(app_args.gd):
            raise Exception("Target game directory does not exist: " + app_args.gd)
        print("Game files directory: " + app_args.gd)
    print("File encoding: " + file_encoding)
    print("Processing " + working_dir + " ...")

    if not os.path.exists(working_dir):
        raise Exception("Working directory does not exist: " + working_dir)


    MT = None
    if app_args.t or app_args.tu or app_args.tdct or app_args.tdctu:
        # MTL bans you if you free-use it faster than N (>5000) chars per T (>10) sec
        # The following methods to be implemented within a custom translator's class

        if ENABLE_CACHE:
            cache = Cache("__pycache__")

        from googletrans import Translator
        print("Using Google API translator...")
        
        do_merge = app_args.nomerge
        # MTL bans you if you free-use it faster than N (>2000) chars per T (>20) sec
        # The following methods can be implemented within a custom translator's class
        if not hasattr(Translator, "wait"):
            def wait(self): sleep(20)
            Translator.wait = wait
        if not hasattr(Translator, "get_char_limit"):
            def get_char_limit(self): return 2000
            Translator.get_char_limit = get_char_limit
        if not hasattr(Translator, "on_finish"):
            def on_finish(self):
                if cache is not None:
                    cache.clear()
                return
            Translator.on_finish = on_finish
        if hasattr(Translator, "translate"):
            translate_old = Translator.translate
            not_translit_mode = False
            def translate_new(self, lines_array, is_seq_strings):
                text_to_translate = '\n'.join(lines_array) + '\n'
                if len(text_to_translate.strip()) == 0: return (0, lines_array)

                transl_text = ''
                text_is_long = len(text_to_translate) > CACHE_MIN_TEXT_LENGTH
                hash = None
                if ENABLE_CACHE and text_is_long:
                    hash = md5(text_to_translate.encode("utf-16le")).hexdigest()
                    transl_text = cache.get(hash)
                    if transl_text is not None:
                        #print(PROGRESS_OTHER_CHAR, end='', flush=True)
                        return (0, transl_text)
                    else:
                        transl_text = ''

                # we need join -> split because there can be multiline items in lines_array
                # in which case l_orig_lines != len(lines_array)
                del lines_array
                l_orig_lines = text_to_translate.splitlines()
                l_orig = len(l_orig_lines)

                translation_types = check_translation_types(l_orig_lines, lang_src, is_seq_strings, not_translit_mode, do_merge)
                text_to_translate = make_text_to_translate(l_orig_lines, translation_types)

                #print(PROGRESS_CHAR, end='', flush=True)
                self.wait()

                while True:
                    try:
                        transl_text = translate_old(self, text_to_translate, src=lang_src, dest=lang_dest).text
                        break
                    except Exception as e:
                        print(str(e), end='\r')
                        sleep(TRANSLATION_BAN_DELAY)

                tr_txt_len = len(transl_text)
                transl_text = transl_text.splitlines()

                # restore empty lines
                transl_text_full = restore_translation_lines(l_orig_lines, transl_text, translation_types, not_translit_mode)
                l_tran = len(transl_text_full)
                if l_orig != l_tran:
                    lines = ''
                    sent_lines = text_to_translate.splitlines()
                    for i, line in enumerate(transl_text_full):
                        try:
                            lines += l_orig_lines[i]
                            lines += f" -({translation_types[i]})-> "
                        except: pass
                        lines += line + '\n'
                    with open('error_translations.log', 'w', encoding=CSV_ENCODING) as dtxt: dtxt.write(lines)
                    raise Exception(f"\nERROR: Mismatch in translated line counts, original={l_orig} new={l_tran}, error_translations.txt written.")

                # if the translation result is shorter don't cache it, it's strange
                if ENABLE_CACHE and (hash is not None) and text_is_long and (tr_txt_len > CACHE_MIN_TEXT_LENGTH):
                    tagstr = 'gtrans'
                    cache.set(hash, transl_text_full, expire=CACHE_EXPIRY_TIME, tag=tagstr)

                return (1, transl_text_full)
            Translator.translate = translate_new

        MT = Translator(raise_exception=True)
        print("Starting time: {}".format(datetime.datetime.now().strftime("%H:%M %d.%m.%Y")))

    OCR = None
    if app_args.ocr:
        OCR = OCRservice()

    all_game_fn = []
    if app_args.ca and app_args.gd and os.path.exists(app_args.gd):
        # list all game files except .git folder
        all_game_fn = sorted(set([os.path.splitext(a)[0].strip()
                       for dp,_,fa in os.walk(app_args.gd)
                       for a in fa
                       if (".git" not in dp) and os.path.isfile(os.path.join(dp, a))]))

    pat_provided = False
    for pat in patterns:
        # for custom patterns like *aaa_*_b.png
        if pat.split('.')[-1] in img_exts:
            if app_args.i or app_args.u:
                # remove image patterns for read/write operations on text files
                patterns.remove(pat)
            else:
                # use custom image patterns
                pat_provided = True

    if not pat_provided and not is_pattern_manual:
        if app_args.tu or app_args.t or app_args.a:
            patterns += image_patterns
        elif app_args.ocr:
            patterns = image_patterns


    FT = FileTranslate(work_dir=working_dir,
                       img_exts=img_exts,
                       file_enc=file_encoding,
                       re_a=regexp_attr, re_s=regexp_txt, re_t=regexp_tag,
                       re_a_sep=regexp_attr_sep,
                       re_excl = regexp_excl,
                       game_dir=app_args.gd,
                       git_origin=(app_args.url if USE_GIT else ''),
                       strip_cmts=True)

    if app_args.isc:
        is_type = 'attributes'
        if app_args.isc == 2: is_type = 'attributes and strings'
        elif  app_args.isc == 3: is_type = 'attributes, strings and in-file lines'
        print(f"Intersecting {is_type}...")
        FT.intersectAttributes(app_args.isc)
        return
    elif app_args.isa:
        is_type = 'attributes'
        if app_args.isc == 2: is_type = 'attributes and strings'
        print(f"Applying intersections to {is_type}: ", end='', flush=True)
        if FT.applyIntersectionAttributes(app_args.isa):
            FT.updateRepo("intersection")
        print('')
        return
    elif app_args.cut:
        print("Applying cutoff marks %s at %s%d characters: " %
              (app_args.cm, ('~' if True else ''), app_args.cut), end='', flush=True)
        FT.applyCutMarks(app_args.cut,
                         cut_chrs=string_unescape(app_args.cm),
                         #mind_chr=' ',
                         #use_bytelength=False
                        )
        print('')
        return
    elif app_args.dct:
        is_type = 'strings'
        if app_args.isc == 2: is_type = 'attributes and strings'
        print(f"Making {is_type} dictionary...", end='', flush=True)
        FT.makeDictionary(app_args.dct)
        return
    elif app_args.tdct or app_args.tdctu:
        print('')
        if app_args.tdct:
            print("Translating dictionary... ")
        else:
            print("Updating dictionary translation... ", end='', flush=True)
        res = FT.translateCSV(MT, os.path.join(working_dir, DICTIOANRY_FILE), False, app_args.tdctu)
        MT.on_finish()
        return

    if USE_GIT:
        if app_args.exp:
            print("Archiving repository to:", FT.archiveRepo())
            return
        elif app_args.commit:# or (app_args.rit and not app_args.nogit):
            print("Commiting repository...")
            FT.updateRepo("commit", to_origin=app_args.commit, silent=(True if app_args.rit else False))
            if app_args.commit: return
        elif app_args.revert:
            print("Reverting repository to ", end='', flush=True)
            FT.revertRepo()
            return

    if app_args.rit:
        old_re = re.compile(r'%s' % app_args.o, re.M | re.U)
        new_str = r'%s' % re.sub(UNICODE_ESCAPE_RE, lambda x: string_unescape(x.group()), app_args.n)
        if app_args.f:
            print("Replacing using replacements database:", os.path.realpath(app_args.f))
        else:
            print("Replacing '%s' to '%s' in translations:" % (old_re.pattern, new_str))

    # Walks through directory structure looking for files matching patterns
    matchingFileList = list(find_files(working_dir, patterns, ["*"+STRINGS_DB_POSTFIX, "*"+ATTRIBUTES_DB_POSTFIX]))
    totalCount = len(matchingFileList)
    print("Found sources (" + ','.join(patterns) +'):', str(totalCount))

    fileCount = 0
    fileAllCount = 0
    for currentFile in matchingFileList:
        if not(os.path.isfile(currentFile) and os.access(currentFile, os.W_OK)):
            print("WARNING: File does not exist or not accessible: " + currentFile)
            continue
        fileAllCount += 1
        res = False
        base_name = currentFile.replace(working_dir, '') + (" (%d of %d)" % (fileAllCount, totalCount))
        currentFile = os.path.abspath(currentFile)
        only_name = os.path.splitext(currentFile)[0]
        if (os.path.basename(__file__) in currentFile) or ("replacers.csv" in currentFile) or ("requirements" in currentFile):
            continue

        if (app_args.i or app_args.a) and (not FT.file_enc or FT.file_enc == ''):
                FT.file_enc = detect_encoding(currentFile)

        if app_args.a:
            print("Applying translation to " + base_name + ' ')
            res = FT.applyTranslationsToFile(currentFile, mode=app_args.a)
        elif app_args.t or app_args.tu:
            if app_args.t:
                print("Translating " + base_name + ' ...\n', end='', flush=True)
            else:
                print("Updating translation of " + base_name + ' ...\n', end='', flush=True)
            res = FT.translateCSV(MT, only_name + ATTRIBUTES_DB_POSTFIX, False, app_args.tu)
            #print(';', end='', flush=True)
            res = True if FT.translateCSV(MT, only_name + STRINGS_DB_POSTFIX, True, app_args.tu) else res
            #res = True if profile_func(translateCSV, MT, only_name + STRINGS_DB_POSTFIX, True, app_args.tu) else res
        elif app_args.ocr:
            print('')
            print("Performing OCR " + base_name + ' ', end='', flush=True)
            res = process_image(OCR, currentFile)
        elif app_args.px or app_args.rx:
            print("Fixing translation of " + base_name + ' ')
            res = prepare_csv_excel(only_name + ATTRIBUTES_DB_POSTFIX, app_args.rx)
            res = True if prepare_csv_excel(only_name + STRINGS_DB_POSTFIX, app_args.rx) else res
        elif app_args.fix:
            print("Fixing translation of " + base_name + ' ')
            res = FT.applyFixesToTranslation(only_name, False)
            res = True if FT.applyFixesToTranslation(only_name) else res
        elif app_args.ca and app_args.gd:
            print("Validating attributes of " + base_name, end='', flush=True)
            res = strip_attr_matching_file(only_name + ATTRIBUTES_DB_POSTFIX, all_game_fn)
            print('')
        elif app_args.i or app_args.u:
            print('')
            if app_args.u:
                print("Upgrading strings " + base_name + ' :', end='', flush=True)
            else:
                print("Making strings " + base_name + ' :', end='', flush=True)
            res = FT.makeTranslatableStrings(currentFile, app_args.u, lang_src + "_ALL")
        elif app_args.rit:
            for csv_file in [(only_name + ATTRIBUTES_DB_POSTFIX), (only_name + STRINGS_DB_POSTFIX)]:
                tmp = FT.replaceInTranslations(csv_file, old_re, new_str, app_args.f)
                if tmp > 0:
                    print(f"Replaced {tmp} times in", csv_file)
                    res = True
        else:
            print("Unexpected parameter combination, aborting...")
            sys.exit(1)
            break
        if res:
            fileCount += 1

    if MT is not None: MT.on_finish()
    print("\nTotal files passed             : " + str(fileCount))

    if USE_GIT and not app_args.nogit:
        try:
            if app_args.i:
                print("Creating or updating Git repo... ", end='', flush=True)
                FT.createRepo()
                print('Ok')
            elif app_args.t or app_args.u or app_args.tu or (
                (app_args.fix and fileCount>0) or app_args.rx): # or app_args.ocr):
                tag = None
                if app_args.t: tag = "translations"
                elif app_args.u: tag = "new strings"
                elif app_args.tu: tag = "new translations"
                elif app_args.fix: tag = "tags and contexts"
                elif app_args.ocr: tag = "image OCRs"
                elif app_args.rx: tag = "after office format revert"
                print("Updating Git repo (" + tag + ')... ', end='', flush=True)
                FT.updateRepo(tag)
                print('Ok')
            elif app_args.u:
                pass
        except Exception as e:
            print('Failed')
            print(repr(e))


if __name__ == "__main__":
    main()
