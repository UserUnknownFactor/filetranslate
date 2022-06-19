# -*- coding: utf-8 -*-
"""
    ocrspace
    ~~~~~~~~

    OCR using OCR.space service with free API key.
"""
__version__ = '0.1.0'

import json, os, csv
from collections import namedtuple
from time import sleep, time
import numpy as np
import urllib3
import requests
from bs4 import BeautifulSoup

DEBUG1 = False
API_KEY_DB = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'apikeys.csv')
CSV_ENCODING = "utf-8-sig"
DELIMITER_CHAR ='→'

csv.register_dialect("apikeys", delimiter=DELIMITER_CHAR, quotechar='', doublequote=False, quoting=csv.QUOTE_NONE)

def get_api_key():
    """Get API key from a corresponding database

    :return: String with API key
    """
    keys = dict()
    keys["ocrspace"] = "helloworld"
    if os.path.isfile(API_KEY_DB):
        with open(API_KEY_DB, 'r', newline='', encoding=CSV_ENCODING) as f:
            keys = dict(csv.reader(f, 'apikeys'))
            print('OCR.space API key is', keys["ocrspace"])
    return keys["ocrspace"]

def tolerance_sort(array, tolerance):
    array_sorted = np.copy(array[np.lexsort((array[:, 0], array[:, 1]))])
    sort_range = [0]
    for i in range(array.shape[0] - 1):
        if array_sorted[i + 1, 1] - array_sorted[i, 1] <= tolerance:
            sort_range.append(i + 1)
            continue
        else:
            sub_arr = np.take(array_sorted, sort_range, axis=0)
            sub_arr_ord = np.copy(sub_arr[np.lexsort(
                (sub_arr[:, 1], sub_arr[:, 0])
                )])
            array_sorted[slice(sort_range[0], sort_range[-1] + 1)] = sub_arr_ord
            sort_range = [i + 1]
    return array_sorted

def merge_close_boxes(boxes, letters, thresh_w=2, thresh_h=2, thresh_s=0.3) -> (list, list):
    if len(boxes) == 0:
        return ([],[])
    boxes = np.array(boxes)
    words = np.array(letters, dtype=('<U{}'.format(len(letters))))
    boxes_ind = np.column_stack((boxes, (boxes[:,2] + 1) * (boxes[:,3] + 1), np.arange(len(boxes)))).astype(np.int)
    letters_ind = np.column_stack((words, np.arange(len(boxes))))
    #letters_ind[:, 1].astype(np.int)
    boxes_merged = boxes_ind#tolerance_sort(boxes_ind, 30)

    i = 0
    picked = []
    # dimensions are x y w h s i
    #horisontal
    while (i < boxes_merged.shape[0]):
        j = 1
        last_x = boxes_merged[i, 0]
        first_x = last_x - boxes_merged[i, 2]
        wd = boxes_merged[i, 2] * thresh_w
        picked.append(i)
        while (i+j < boxes_merged.shape[0]):
            #m_1 = min(boxes_merged[i + j, 4], boxes_merged[i, 4])
            #m_2 = max(boxes_merged[i + j, 4], boxes_merged[i, 4])
            dif_x = boxes_merged[i + j, 0] - last_x
            last_x = boxes_merged[i + j, 0]
            if ( #m_1 / m_2 >= thresh_s and
                dif_x > 0 and
                dif_x < wd
               ):
                boxes_merged[i, 3] = max(boxes_merged[i+j, 3], boxes_merged[i, 3])
                boxes_merged[i, 1] = min(boxes_merged[i+j, 1], boxes_merged[i, 1])
                boxes_merged[i, 2] = boxes_merged[i+j, 0] - first_x
                letters_ind[int(boxes_merged[i, 5]), 0] += letters_ind[int(boxes_merged[i+j, 5]), 0]
                j += 1
            else:

                break
        i += j
    '''
    #vertical
    while (i < boxes_merged.shape[0]):
        j = 1
        last_x = boxes_merged[i, 0]
        first_x = last_x - boxes_merged[i, 2]
        wd = boxes_merged[i, 2] * thresh_w
        picked.append(i)
        while (i+j < boxes_merged.shape[0]):
            #m_1 = min(boxes_merged[i + j, 4], boxes_merged[i, 4])
            #m_2 = max(boxes_merged[i + j, 4], boxes_merged[i, 4])
            dif_x = boxes_merged[i + j, 0] - last_x
            last_x = boxes_merged[i + j, 0]
            if ( #m_1 / m_2 >= thresh_s and
                dif_x > 0 and
                dif_x < wd
               ):
                boxes_merged[i, 3] = max(boxes_merged[i+j, 3], boxes_merged[i, 3])
                boxes_merged[i, 1] = min(boxes_merged[i+j, 1], boxes_merged[i, 1])
                boxes_merged[i, 2] = boxes_merged[i+j, 0] - first_x
                letters_ind[int(boxes_merged[i, 5]), 0] += letters_ind[int(boxes_merged[i+j, 5]), 0]
                j += 1
            else:

                break
        i += j
    '''

    # return only the bounding boxes that were picked
    #boxes_merged = boxes_merged[boxes_merged[:,4].astype(np.int)]
    #letters_ind = letters_ind[boxes_merged[:,4].astype(np.int)]
    boxes_merged = boxes_merged[picked]
    letters_ind = letters_ind[boxes_merged[:,5].astype(np.int)]
    boxes_merged = np.delete(boxes_merged, np.s_[4:6], 1).astype(np.int)
    letters_ind = np.array(np.delete(letters_ind, np.s_[1:2], 1)).reshape(-1)
    return boxes_merged.tolist(), letters_ind.tolist()

class OCRspace:
    # It would be better to use local tesseract OCR but meh...
    def __init__(self, language='jpn', overlay=True):
        """ OCR.space API init.
        :param api_key: OCR.space API key. Get it here: https://ocr.space/ocrapi#free
                        Please use your personal key if there are >500 requests per month.
        :param language: Language 3-letter code to be used in OCR.
                        List of available codes: https://ocr.space/ocrapi#language
                        Defaults to 'jpn'.
        :param overlay: Is OCR.space overlay required in your response. Defaults to True.
        """ 
        self.s = requests.session()
        self.headers_get = {
            'cache-control': "no-cache",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:73.0) Gecko/20100101 Firefox/73.0',
            'Referer': 'https://ocr.space/',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://ocr.space'
        }
        self.api_key = get_api_key()
        self.language = language
        self.overlay = overlay
        self.delay = 8640 # API limits us to less than that (seconds)
        self.max_size = 1024000

    def ocr(self, filename) -> (list, list):
        """ OCR.space request with local file.

        :param filename: Your image path.
        :return: (ocr_boxes: list, ocr_strings: list)
        """
        # debug: load cached response
        if DEBUG1 and os.path.isfile(filename + '.pckl'):
            with open(filename + '.pckl', 'r', encoding='utf-8-sig') as f:
                r = json.load(f)
                coords = []
                words = []
                for line in r["ParsedResults"][0]["TextOverlay"]["Lines"]:
                    for word in line["Words"]:
                        words.append(word["WordText"])
                        coords.append([word["Left"],
                                    word["Top"],
                                    word["Width"],
                                    word["Height"]])
                return merge_close_boxes(coords, words)

        with open(filename, 'rb') as f:
            old_file_position = f.tell()
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(old_file_position, os.SEEK_SET)
            if size >= self.max_size:
                print("ERROR: Size of image must be less than 1024 KB (free-mode)")
                return ([], [])
            payload = {'isOverlayRequired': self.overlay,
                        'apikey': self.api_key,
                        'language': self.language,
                        'FileType': '.Auto',
                        'IsCreateSearchablePDF': False,
                        'detectOrientation': False,
                        'scale': True,
                        'OCREngine': 1,
                        'detectCheckbox': False,
                        'checkboxTemplate': 0
                        }
            imgtemp = 'f' + str(int(time())) + os.path.splitext(filename)[1]
            r = self.s.post('https://api.ocr.space/parse/image', files={imgtemp: f}, data=payload)
            r.encoding = 'utf-8'
            r = r.json()
            # debug: cache response
            if DEBUG1 and not os.path.isfile(filename + '.pckl'):
                with open(filename + '.pckl', 'w', encoding='utf-8-sig') as f:
                    json.dump(r, f)

        if (not r) or isinstance(r, str) or int(r["OCRExitCode"]) != 1:
            res = r if isinstance(r, str) else str(r["OCRExitCode"])
            print("ERROR: %s" % res, end='')
            #print(r)
            return ([], [])
        else:
            coords = []
            words = []
            strings = []
            if not r["ParsedResults"][0] or len(r["ParsedResults"][0]["ParsedText"]) < 1:
                return (coords, words)

            for line in r["ParsedResults"][0]["TextOverlay"]["Lines"]:
                strings.append(line["LineText"])
                for word in line["Words"]:
                    words.append(word["WordText"])
                    coords.append([word["Left"],
                                word["Top"],
                                word["Width"],
                                word["Height"]])

            return merge_close_boxes(coords, words)
