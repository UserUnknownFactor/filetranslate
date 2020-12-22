import re, csv, os
import chardet

DELIMITER_CHAR = '→'
ESCAPE_CHAR = '¶'
USE_CR_REPLACER = False
CARRIAGE_RETURN_REPLACER = '▒' #\u2592
CARRIAGE_RETURN = '\x0D'
CSV_ENCODING = "utf-8-sig"

MAX_LINES_CHARDET = 100 # reasonable depth of first foreign characters (lines)

FULL_RE = r'((?:\\(?:b|t|n|f|r|\"|\\)|\\'
PART_RE = r'((?:\\'
ESCAPECHARS_RE = re.compile(FULL_RE + r'(?:(?:[0-2][0-9]{1,2}|3[0-6][0-9]|37[0-7]|[0-9]{1,2}))|\\(?:u(?:[0-9a-fA-F]{4,8})))+)')

DIALECT_EXCEL = "excel"
DIALECT_TRANSLATION = "translation"
csv.register_dialect(DIALECT_EXCEL, delimiter='\t', doublequote=False, quoting=csv.QUOTE_NONE, escapechar='"', lineterminator='\n')
csv.register_dialect(DIALECT_TRANSLATION, delimiter=DELIMITER_CHAR, quotechar='', doublequote=False, quoting=csv.QUOTE_NONE, escapechar=ESCAPE_CHAR, lineterminator='\n')

LAST_NEWLINE_RE = re.compile(r"([^\n])[\n]$")

def chomp(x):
    """Removes last linebreak after a character."""
    LAST_NEWLINE_RE.sub(r'\1', x)
    return x


def num_groups(aregex):
    """Counts groups in regexp."""
    return re.compile(aregex).groups


def merge_dicts(*dict_args):
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def preprocess_in(lines, replace_cr):
    for line in lines:
        if replace_cr:
            yield line.replace(CARRIAGE_RETURN, CARRIAGE_RETURN_REPLACER)
        else:
            yield line


def preprocess_out(lst, replace_cr):
    for row in lst:
        if replace_cr:
            yield [(col.replace(CARRIAGE_RETURN_REPLACER, CARRIAGE_RETURN) if isinstance(col, str) else col) for col in row]
        else:
            yield row


def read_csv_list(fn, ftype=DIALECT_TRANSLATION, replace_cr=USE_CR_REPLACER):
    if os.path.isfile(fn):
        with open(fn, 'r', newline='', encoding=CSV_ENCODING) as f:
            return list(x for x in csv.reader(preprocess_in(f, replace_cr), ftype) if len(x) > 0)
    else:
        return list()


def write_csv_list(fn, lst, ftype=DIALECT_TRANSLATION, replace_cr=USE_CR_REPLACER):
    if not lst or len(lst) == 0: return
    with open(fn, 'w', newline='', encoding=CSV_ENCODING) as f:
        writer = csv.writer(f, ftype)
        for row in preprocess_out(lst, replace_cr):
            writer.writerow(row)


def read_csv_dict(fn, ftype=DIALECT_TRANSLATION, replace_cr=USE_CR_REPLACER):
    if os.path.isfile(fn):
        with open(fn, 'r', newline='', encoding=CSV_ENCODING) as f:
            # the function will ignore columns after second
            return {item[0]: item[1] for item in csv.reader(preprocess_in(f, replace_cr), ftype) if len(item) > 1}
    else:
        return dict()


#def string_unescape(s, enc="utf-8"):
#    return (bytes(s.encode("latin-1", "backslashreplace").decode("unicode_escape"), encoding=enc).decode(enc))
def string_unescape(s, encoding="utf-8"):
    """Unescapes backslash-escaped character sequences in strings.
    """
    """
    sarray = ESCAPECHARS_RE.split(s)
    for i, si in enumerate(sarray):
        if ESCAPECHARS_RE.search(si):
            sarray[i] = si.encode("latin1").decode("unicode-escape")
    return ''.join(sarray)
    """
    return s.encode(encoding).decode( 'unicode-escape' )

def detect_encoding(file_name):
    """Detects encoding of a text file, returns "cp932" if failed.
    """
    with open(file_name, "rb") as x:
        line = x.readline()
        count = 0
        testStr = ''
        while line and count < MAX_LINES_CHARDET:
            testStr = testStr + line
            count += 1
            line = x.readline()
    enc = chardet.detect(testStr)
    if enc and enc["encoding"]: enc = enc["encoding"]
    else: enc = "cp932"
    return enc
