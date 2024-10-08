﻿# Game File Translation Tool:<br/>filetranslate

Tool for the entire process of collaborative game translation from Japanese to English
using Machine Translation (MTL) and Optical Character Recognition (OCR).

## Installation

```Text
pip install .
```

## Usage

```Text
filetranslate [-h] [-e encoding] [-p file_patterns] [-g game_engine]
        [-ra attr_regexp] [-rs text_regexp] [-rt tag_regexp] [-rex exc_regexp]
        [-lang language_pair] [-gd game_files_path] [-cm cut_mark] [-nomerge] [-remnl]
        [-images] [-acolor alpha_color] [-svg [svg_params]] [-dist box_dist] [-font cut_font_info] 
        [-i | -u | -ocr [OPT] | -t | -tu | -fix | -cut [N] | -a [mode] | -cmp]
        [-rit] [-o old_regexp] [-n new_replacer] [-ifs orig_allow_re] [-exs orig_block_re] [-f replacers_file] 
        [-ca | -isc [type] | -isa [type] | -dct [type] | -tdct | -tdctu] 
        [-url git_origin] [-commit [type] | -revert | -exp |-nogit]
        [-px | -rx]

options:
  -h, --help           show this help message and exit
  -e encoding          Original encoding (ex: cp932, cp1252 etc; utf-8 by default)
  -p file_patterns     File patterns (ex: *.txt,*.json)
  -g game_engine       Game engine preset (tyrano, kirikiri, kirikiri_tjs, rpgmakermv, rpgmakerace_scripts, rpgmakerace_yaml,
                       godot, godot_dialogic, resources)
  -lang language_pair  Translation direction pair SRC-DEST (ex/def: JA-EN)
  -gd game_files_path  Directory of the original game files
  -cm cut_mark         Cut-mark string or character
  -nomerge             Don't merge partial sequential strings during translation
  -remnl               Remove newlines from source strings
  -drop                Remove originals if the translation is empty
  -images              Process all image files
  -acolor alpha_color  OCR color replacer for alpha channel (ex/def: #000000)
  -svg [svg_params]    Generate SVGs with positioned text for each OCR result
  -dist box_dist       Maximal horizontal/vertical distances to merge OCR textboxes (ex: 10,10)
  -font cut_font_info  Default font for pixel width measurement when -cut >128 (ex/def: msgothic.ttc,24)
  -bin bin_exts        Binary file extensions (ex/def: .exe,.dll)
  -pf_pat preformat    Sets format for string pre-formatting with context (ex/def: %s: %s)
  -pf                  Enables pre-formatting of strings sent to MTL to mix context in them
  -ts                  Check .csv files for changes and process only changed

file regexps:
  -ra attr_regexp      RegExp for attributes
  -rs text_regexp      RegExp for texts
  -rt tag_regexp       RegExp for text tags
  -rex exc_regexp      RegExp for text exclusion

stage:
  -i                   Initialize translation files
  -u                   Update translation files for new strings
  -ocr [OPT]           Perform text recognition for images (1: default, 2: invert, 4: binarize; can be sum)
  -t                   Perform initial string translation
  -tu                  Perform translation of new strings
  -fix                 Revert replacement tags and apply translation_dictionary_out to translation
  -cut [N]             Add cut-mark character after N-letters or N-pixels in the given font, if N>128
  -a [mode]            Apply translation to original files (1: skip existing (def), 2:replace; apply dictionary_out to 4:
                       strings, 8: attributes; 16: all file content; can be sum)
  -cmp                 Make translations from two language versions (root and to_compare folders)

replacement:
  -rit                 Replace text in translations by RegExp (used with -f or both -o and -n options)
  -o old_regexp        RegExp for old translated text
  -n new_replacer      New translated text RegExp replacer
  -ifs orig_allow_re   RegExp for replacement check vs original
  -exs orig_block_re   RegExp for exclusion check vs original
  -ifc context_re      RegExp for check vs context
  -f replacers_file    Replacers DSV database (ex: replacers.csv)

additional:
  -ca                  Comment attributes with corresponding game file (checks if an attribute matches a filename and comments if it is)
  -isc [type]          Create intersection of strings in files (1:attributes, 2:+strings, 3:+infile-duplicates (def))
  -isa [type]          Apply intersection file to translations (1:attributes, 2:+strings (def))
  -dct [type]          Make dictionary file from all original words (1:strings (def), 2:+attributes)
  -tdct                Translate dictionary file
  -tdctu               Update translation of dictionary file

git:
  -url git_origin      Git origin URL
  -commit [type]       Commit changes to the repository (1:local (def), 2:origin)
  -revert              Reverts ALL changes, if not committed, otherwise reverts to the previous commit
  -exp                 Export git repository as a zip file
  -nogit               Disable Git usage

excel:
  -px                  Prepare for Excel or OpenOffice (√ = tab, ∞ = newline)
  -rx                  Revert Excel or OpenOffice compatibility for -a and -fix options
```

## Translation steps

1. Extract the game resources using existing or a new unpack tool.
1. Create a separate folder for the project.
1. Copy folders and files to be translated into the project folder.
1. Create and validate (I use regex101.com for that) Regular Expressions to detect:

    * Translatable node attributes;
    * Translatable strings and their context (like the current character name; context is optional);
    * Tags inside strings that shouldn't be translated;
    * Strings that don't need to be translated (exclusion expression);
    * Strings that can be merged (only through  `game_regexps.csv`);
1. Change current directory to the project folder.
1. Using `-ra`, `-rs`, `-rt`, `-e`, `-p` and `-i` parameters of `filetranslate` extract strings to be translated from game files into `%filename%_attributes.csv` and `%filename%_strings.csv` files.  
Alternatively use an entry in `game_regexps.csv` for the game engine patterns and use `-g <game_engine>` parameter with the registered engine (may require existing regular expressions fine-tuning). You can also create `%game_engine%.project` file in the project folder to automatically pick the engine every time you run `filetranslate` from that folder. The project file's first line can contain the game's path for `-gd` option (not recommended for transferred projects).  
**WARNING**: Running filetranslate with `-i` parameter overwrites existing translation files so if you're planning to reinitialize the project backup them beforehand.
1. _(alpha)_ Use `-ocr` parameter to perform OCR on images. It uses [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) for the recognition.
1. Create and(or) modify `replacement_tags.csv` and `translation_dictionary_in.csv` databases. 
Look through the entire Japanese text and move most common names, places, and sound effects to `translation_dictionary_in.csv`, and translate them manually because machine translator will botch them for sure. It may take two translation passes with the project reinitialization in-between or specific research to do that.
It may be helpful to write replacements in kana for some known words used in many places.
Check DSV format description below (by default: `original→replacement`).  
Move important tags from `replacement_tags.csv` to `translation_dictionary_in.csv` and correspondingly to `translation_dictionary_out.csv` while escaping RegExp characters because `replacement_tags.csv` can be rewritten on `-i` run.
1. Use `-t` parameter to perform machine translation of strings and recognized images' strings (with `-images` parameter).
1. Check translations to see what may need correction and
fill `translation_dictionary_out.csv` with proper replacements.
1. Perform `-ca` run with `-gd <game files directory>` parameter pointing to actual game files directory to comment out attributes for which there exists a corresponding file. You'll need to transfer their translations manually to be on the safe side.
1. Perform `-isc` run to detect intersecting strings mentioned in multiple files, they are written to `intersections.csv`. Additional parameter `type` specifies what to process: 1 - process only attribute files, 2 - process string and attribute files, 3 - is equal to 2 but additionally adds duplicate strings in the string translation files to intersections.
1. Fix translations in `intersections.csv`.
1. Perform `-isa` run to apply intersecting strings back to translation databases. Use 2 as the parameter to apply string translation file intersections.
1. Revert tags, fix contexts, and apply `translation_dictionary_out.csv` using `-fix` option.
1. Replace wrongly translated repeating words and phrases using `-rit` option supplying RegExp for original translated text in `-o` and replacement in `-n` options. Lines containing spaces should be double-quoted. You can also use `\uXXXX` Unicode escape codes for characters outside the console encoding. Additionally you can allow only on condition or prevent replacement based on the original untranslated string with optional `-ifs`, `-ifc` and `-exs` options correspondingly.
1. Manually fix the resulting translations in corresponding `.csv` files.
1. Apply translations to the game files with `-a` parameter.

    * The `-gd <game files directory>` parameter provided or game path written inside the `.project` file makes `-a` run copy results directly into the game folder (not really recommended).
1. Move `translation_out` content to the game folder with overwriting or run game-specific steps to enable the translation.
1. Test run the game and fix translation `.csv` files again.
1. Repeat the previous five steps until the game works as expected.
1. If the game doesn't support word-wrapping use `-cut [N]` option with the game-specific cut-mark sequence (`-cm` parameter) to break translations at N characters each if N<=128 or otherwise N-pixels each of rendered text in a specific font (`MS Gothic, 24pt` by default; can be specified using `-font` parameter).
1. Copy `.csv` files with their directory structure to an archive or use `-exp` option to backup or share the project.

*Example folder structure of a translation project:*

```
filetranslate_game
├───scenario <- folder with translatable files
│   ├───00_tutorial
│   │ file1.txt
│   │ file2.txt
│   │ file2_attributes.csv <- attributes translations file
│   │ file2_strings.csv <- strings translations file
│   ├───01_base
│   │ file1.txt
│   ├───02_maps
│   │ file1.txt
├───translation_out <- folder with translated files
│   ├───scenario <- copy of the original folder structure
│   │   ├───00_tutorial
│   │   │ file2.txt
│ .gitignore <- file to ignore files and folders with GIT
│ build.cmd <- simple `filetranslate -a 2` run automation
│ game_regexps.csv <- project descriptions file
│ replacement_tags.csv <- auto-generated tag replacements for MTL
│ translation_dictionary_in.csv <- manual regexp replacements for MTL
│ translation_dictionary_out.csv <- manual regexp replacements for fixing texts after
│ gameengine.project <- project type indicator file; first line can provide path to the game folder
```

## Using GitPython

For gitpython package to work GIT needs to be installed separately:  
https://git-scm.com/downloads

The program is currently sensitive to line separator type so there should be only Unix-type separators (LF) in the translation files. AutoCRLF option of git should be `none` because of that.

## Working with multi-line source/target strings and OpenOffice or Excel

1. Use `-px` parameter to prepare translation databases.
1. Use your table editor to modify translations.
1. Revert translation databases with `-rx` parameter before applying or fixing them.

## Translating exe/dll files

0. Extract translatable strings into a DSV file; its format is: `original→translation[→context→[hex offset][,encoding[,escaped filler char like \x20]]]`
1. Create additional line in `game_regexps.csv` (example: `game_1→utf-16le→*.exe→→→`)
2. Optionally create `game_1.project` to automate game engine selection if only .exe is translated.
3. Optionally specify binary extensions with `-bin` parameter like `-bin ".resource"`.
4. Run `filetranslate -g game_1 -a` or `filetranslate -a` if you created the project file.

## Translation update steps

0. Backup translation databases and game files in the project folder.
1. Copy newer game files into the project folder with overwriting.
2. Update translation files with `-u` parameter.
3. Update string translations with `-tu` parameter.
4. Perform corresponding follow-up steps from the main list.

## Applying external project

1. Create an empty project folder.
1. Unpack game scripts/images and copy into that directory.
1. Initialize the project with `-i` option.
1. Copy translation project files to the same folder with overwriting and preserving the directory structure (it should be the same as original game files).
1. Apply translations to the files with `-a` command.
1. Copy `translation_out` content to the game folder or run game-specific steps to enable the translation.

### Additional information and reminders

* Initial translation step (with `-t` parameter) skips files when translated strings found in corresponding `.csv` files;

* Command line parameters take priority over database entries so if you specify `-p File.ext` only this file will be processed.

* Edit translation files `%filename%_attributes.csv` and `%filename%_strings.csv`,
     not files from `\translation_out`, to future-proof your project;

* Always verify RegExp's validity after changing them;

* You can update a series of files with the same original strings at once by fully translating one and copying its content it to `intersections.csv` in the project root then running `-isa` command.

### Special databases (DSVs column-separated by `→` with quote character `¶`)

#### For automated processing

* `game_regexps.csv`: DSV file with game-specific file encodings, file masks, and RegExp patterns; RegExps in this file can be multiline (with newlines ¶-quoted) all lines will be merged on load; 

  * The game database is searched in the project folder first and in the module installation folder second.
  * The game database entry format (see the existing file for more examples):  
    `Engine/project name→File encoding→Comma separated file masks (ex: *.json,*.txt)→Attribute regexp→Main text regexp with capturing groups for context: (?P<context>) and main string: (?P<text>)→Tags regexp→Exclusion regexp→Merge regexps; || separated`
  * The main text RegExp should contain consequent capturing groups like `(preamble_start(context)preamble_end)?(...)(main text)(...)`. The main text and context are detected by their group names. The capture groups should capture the entire data block with no uncaptured elements. Only context can be an embedded group.
  * Attribute RegExps must contain one capture group for each attribute text while the rest of the RegExps don't use groups.
  * Attribute RegExps can be two parts separated by `|<===>|` where first part is attribute expression with as many capture groups as needed and second part is additional processing of result of the first expression (like double-quoted attribute lists within a command in RPGM MV).
  * Merge RegExp is three parts separated by `||`:

      * Generic specification if the line allowed to be merged; for example `[^;…。？！）\.\]]$`
      * Stuff that's blocking for merging the previous line in the start tags/text of the next line; for example `(?:^[（「\\])`
      * Stuff that's blocking for merging the next line in the end tags/text of the previous line; for example `(?:[」）]$)`

* `replacement_tags.csv`: DSV file with text tags automatically found in strings. Replace commas with `:.?!` to help MTL position them.
    When sending strings to MTL, `replacement_tags.csv` has priority.

#### For manual fixes

* `translation_dictionary_in.csv`: DSV file with replacements in RegExp format before translating text (jpn → eng, jpn → empty or jpn → jpn);

* `translation_dictionary_out.csv`: DSV file with replacements in RegExp format for `-fix` and `-a` options, in the latter case it's applied to the original file with the corresponding parameter;

* `intersections.csv`: DSV file with duplicate strings found in multiple translation files.

* `dictionary.csv`: DSV file with dictionary of words found in multiple translation files.