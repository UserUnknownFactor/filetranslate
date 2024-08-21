import re
import pefile

def read_binary_file(file_path):
    code_section_end = 0
    pe = pefile.PE(file_path)
    code_section = None
    for section in pe.sections:
        if b'.text' in section.Name:
            code_section = section
            break
    if code_section is not None:
        code_section_va = code_section.VirtualAddress
        code_section_size = code_section.SizeOfRawData
        code_section_end = code_section_va + code_section_size
        pe.close()
    else:
        print("Code section not found")
    with open(file_path, 'rb') as file:
        if code_section_end:
            print(f"Skipping to 0x{code_section_end:X}")
        file.seek(code_section_end)
        return file.read()

def extract_strings(data, encoding):
    if 'utf-16' in encoding:
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
file_path = 'file.exe'
strings = extract_strings(read_binary_file(file_path), 'utf-16le')
with open("strings.txt", "w", encoding="utf-8-sig") as o:
    o.write("\n".join(strings))
