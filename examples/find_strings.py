import re

def read_binary_file(file_path):
    with open(file_path, 'rb') as file:
        return file.read()

def extract_strings(data, encoding):
    if encoding == 'utf-16le':
        delimiter = b'\x00\x00'
        min_length = 8  # Minimum length for UTF-16LE (including null-terminator)
    else:  # cp932
        delimiter = b'\x00'
        min_length = 5  # Minimum length for CP932 (including null-terminator)

    strings = []
    start = 0
    while True:
        end = data.find(delimiter, start)
        if end == -1:
            break
        if end - start >= min_length:
            try:
                string = data[start:end].decode(encoding)
                if validate_string(string):
                    strings.append(string.replace('\r', '\\r').replace('\n', '¶\n') + '→')
            except UnicodeDecodeError:
                pass
        start = end + len(delimiter)
    return strings

def validate_string(string):
    valid_pattern = re.compile(r'[\u3041-\u3096\u30A0-\u30FF\u3400-\u4DB5\u4E00-\u9FCB\uF900-\uFA6A\u2E80-\u2FD5\uFF5F-\uFF9F\u3000-\u303F\u31F0-\u31FF\u3220-\u3243\u3280-\u337F\uFF01-\uFF5E\u2026-\u203Ba-zA-Z\d\s.,!?()\-\[\[\!@#\$%\^&\*:;\n\'\"()_\+=,\.\/?\\\|\[\]`~]+')
    return bool(valid_pattern.match(string))
    
# Usage example:
file_path = 'file.bin'
strings = extract_strings(open(file_path, "rb").read(), 'cp932')
with open("file_strings.csv", "w", encoding="utf-8") as o:
    o.write("\n".join(strings))
