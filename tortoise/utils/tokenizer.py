import os
import re
import json
import string
import csv
import inflect
import torch
from tokenizers import Tokenizer
from urllib.parse import urlparse
from pathlib import Path
import sys
# Regular expression matching whitespace:
from unidecode import unidecode
from collections import defaultdict
from transformers import pipeline

# NEMO
# Enable this for using nemo text normalisation
NEMO = True
DIR_PATH = os.path.dirname(os.path.abspath(__file__))
NEMO_SRC_DIR = os.path.join(Path(DIR_PATH).parent.parent.parent, 'NEMO')
NEMO_CONFIG_PATH = os.path.join(NEMO_SRC_DIR, "conf/duplex_tn_config.yaml")
print("Module path: ", NEMO_SRC_DIR)
sys.path.append(NEMO_SRC_DIR)

from inference import nemo_model, nemo_infer

# ABBREVIATIONS
INDIAN_ABBREVIATIONS = os.path.join(Path(DIR_PATH).parent, 'data/indian_abbreviations.csv')
INTERNATIONAL_ABBREVIATIONS = os.path.join(Path(DIR_PATH).parent, 'data/international_abbreviations.csv')
ENGLISH_DICTIONARY = os.path.join(Path(DIR_PATH).parent, 'data/words_alpha.txt')

# RoBERTa model for getting abbreviations in text
ROBERTA = True

def get_abbreviation(pipe,text):
    
    output = pipe(text)
    if len(output) == 0:
        return []
    
    concatenated_output = [] 
    for i in range(len(output)):
        entry = output[i]
        if i > 0 and entry['start'] == output[i - 1]['end']:
            # Concatenate the words if the conditions are met
            concatenated_output[-1]['word'] += entry['word']
            concatenated_output[-1]['end'] = entry['end']
        else:
            # If conditions are not met, add the current entry to the output
            concatenated_output.append(entry)
            
    abbrasive_words = [entry['word'].lstrip('Ġ') for entry in concatenated_output if entry['entity'] == 'B-AC' and entry.get('score', 0) > 0.8]
    
    return list(set(abbrasive_words))

_whitespace_re = re.compile(r'\s+')

# List of (regular expression, replacement) pairs for abbreviations:
_abbreviations = [(re.compile('\\b%s\\.' % x[0], re.IGNORECASE), x[1]) for x in [
  ('mrs', 'misess'),
  ('mr', 'mister'),
  ('dr', 'doctor'),
  ('st', 'saint'),
  ('co', 'company'),
  ('jr', 'junior'),
  ('maj', 'major'),
  ('gen', 'general'),
  ('drs', 'doctors'),
  ('rev', 'reverend'),
  ('lt', 'lieutenant'),
  ('hon', 'honorable'),
  ('sgt', 'sergeant'),
  ('capt', 'captain'),
  ('esq', 'esquire'),
  ('ltd', 'limited'),
  ('col', 'colonel'),
  ('ft', 'fort'),
]]

_currency_mapping = {
  '€': 'euro',
  '¥': 'yen',
  'L': 'albanian lek',
  'CHF': 'swiss franc',
  'AU$': 'australian dollar',
  'CA$': 'canadian dollar',
  'CN¥': 'chinese yuan',
  '₽': 'ruble',
  '₩': 'won',
  'R$': 'brazilian real',
  'Mex$': 'mexican pesos',
  '﷼': 'saudi riyal',
  'د.إ': 'dirham',
  '₪': 'shekel',
  '₺': 'lira',
  'kr': 'krona',
  'NZ$': 'new zealand dollar',
  'S$': 'singapore dollar',
  'HK$': 'hong kong dollar',
  'RM': 'malaysian ringgit',
  '₦': 'nigerian naira',
  'CL$': 'chilean peso',
  'COL$': 'columbian peso',
  'Bs': 'venezuelan bolivar',
  'лв': 'bulgerian lev',
  '₴': 'ukrainian hryvna'
}

_math_symbols = {
  'α': 'alpha',
  'β': 'beta',
  'γ': 'gamma',
  'Ρ': 'rho',
  'ρ': 'rho',
  'Υ': 'upsilon',
  'υ': 'upsilon',
  'θ': 'theta',
  '½': 'one half',
  '+': 'plus',
  # removing - as minus because in most cases it's used as - in word, not as minus
  #'-': 'minus',
  '×': 'multiplication',
  '*': 'asterisk',
  '÷': 'division',
  '=': 'equal',
  '%': 'percent',
  '<': 'less than',
  '>': 'greater than',
  '≤': 'less than or equal to',
  '≥': 'greater than or equal to',
  '≠': 'not equal',
  '∑': 'summation',
  '∫': 'integration',
  '√': 'square root',
  '^': 'exponent',
  'π': 'pi',
  '°': 'degree',
  '∞': 'infinity',
  '∈': 'is an element of',
  '∀': 'for all',
  '∃': 'exists',
  '(': ' ', # ')' removed by emoji re, removing '(' here
}

_pronoun_list = {
  "xiaomi": "shau mee",
  "nvidia": "en vi dee aa"
}

_capitalization_list = [
  'IOC', 'USD', 'CEO', 'DJ', 'US', 'RBI', 'UTC', 'HTTP', 'HTTPS', 'AP', 'T20', 'ACA-VDCA', 'AQI', 'CDC', 'ICC'
]

## ADDING ABBRIVATIONS FROM CSV FILE
def read_csv(csv_file_path):
    initialism_list = []
    acronym_dict = {}

    # Read the CSV file
    with open(csv_file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            abbreviation = row["Abbreviation"]
            full_form = row["Full-Form"]
            abbreviation_type = row["Type"]
            pronunciation = row.get("Pronunciation", "")

            if abbreviation_type == "initialism":
                initialism_list.append(abbreviation)
            elif abbreviation_type == "acronym":
                if pronunciation == "":
                    acronym_dict[abbreviation] = abbreviation
                else:
                    acronym_dict[abbreviation] = pronunciation

    return initialism_list, acronym_dict
  
def build_eng_dictionary(dict_txt_filepath):
  '''
  Builds a set of dictionary eng words that are used to check if word is in
  dict or not
  '''
  with open(dict_txt_filepath, 'r') as f:
    lines = f.readlines()
    # already sorted in file
    words = [line.strip() for line in lines]
  
  # set for faster checking of "in"
  eng_dict = set(words)
      
  return eng_dict


indian_initialisms_list, indian_acronyms_dict = read_csv(INDIAN_ABBREVIATIONS)
international_initialisms_list, international_acronyms_dict = read_csv(INTERNATIONAL_ABBREVIATIONS)

##Total initialisim list and acronym dict
_intialisms = indian_initialisms_list + international_initialisms_list + _capitalization_list
_acronyms = {**indian_acronyms_dict, **international_acronyms_dict}
_eng_words_dict = build_eng_dictionary(ENGLISH_DICTIONARY)

def expand_abbreviations(text):
  for regex, replacement in _abbreviations:
    text = re.sub(regex, replacement, text)
  return text

EMOTICON_JSON = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../data/emoticon_dict.json')
with open(EMOTICON_JSON, 'r') as f:
  emoticon_dict = json.load(f)

_inflect = inflect.engine()
_comma_number_re = re.compile(r'([0-9][0-9\,]+[0-9])')
_decimal_number_re = re.compile(r'([0-9]+\.[0-9]+)')
_pounds_re = re.compile(r'£([0-9\,]*[0-9]+)')
_dollars_re = re.compile(r'\$([0-9\.\,]*[0-9]+)')
_rupees_re = re.compile(r'([0-9\.]*[0-9]+)\s*₹|₹\s*([0-9\.]*[0-9]+)')
_units_re = re.compile(r'\b(\d+)\s*(ft|in|cm|m|km)\b')
#_percent_re = re.compile(r'\b(\d+)\s*(%)')
_ordinal_re = re.compile(r'[0-9]+(st|nd|rd|th)')
_number_re = re.compile(r'[0-9]+')
_emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           "]+", flags=re.UNICODE)
#_emoticon_pattern = r'[:;][-]*[)D]|//'
_emoticon_pattern = re.compile(u'(' + u'|'.join([k for k in emoticon_dict] + ['//']) + u')')
currency_symbols = '|'.join(re.escape(symbol) for symbol in _currency_mapping.keys())
_currency_pattern_generic = re.compile(rf'([0-9\.]*[0-9]+)\s*\b({currency_symbols})\b|\b({currency_symbols})\b\s*([0-9\.]*[0-9]+)')
_math_symbols_pattern = re.compile('|'.join(map(re.escape, _math_symbols.keys())))
# translator to remove punctuations from string
_punct_remove_trnslt = str.maketrans("", "", string.punctuation)
_replace_dot_in_words = re.compile(r'(?<=\w)\.(?=\w)')
_pronoun_re = re.compile(r'\b(?:' + '|'.join(re.escape(word) for word in _pronoun_list.keys()) + r')\b', re.IGNORECASE)

def is_url(string):
    return string.startswith('http') or string.startswith('https') or \
      string.startswith('ftp') or string.startswith('fpts') or \
      string.startswith('localhost')

def _remove_commas(m):
  return m.group(1).replace(',', '')


def _expand_decimal_point(m):
  return m.group(1).replace('.', ' point ')


def _expand_dollars(m):
  match = m.group(1)
  parts = match.split('.')
  if len(parts) > 2:
    return match + ' dollars'  # Unexpected format
  dollars = int(parts[0]) if parts[0] else 0
  cents = int(parts[1]) if len(parts) > 1 and parts[1] else 0
  if dollars and cents:
    dollar_unit = 'dollar' if dollars == 1 else 'dollars'
    cent_unit = 'cent' if cents == 1 else 'cents'
    return '%s %s, %s %s' % (dollars, dollar_unit, cents, cent_unit)
  elif dollars:
    dollar_unit = 'dollar' if dollars == 1 else 'dollars'
    return '%s %s' % (dollars, dollar_unit)
  elif cents:
    cent_unit = 'cent' if cents == 1 else 'cents'
    return '%s %s' % (cents, cent_unit)
  else:
    return 'zero dollars'
  
def _expand_rupees(m):
  # 1 if rs at start otherwise 2
  match = m.group(1) or m.group(2)
  #match = m.group(1)
  parts = match.split('.')
  if len(parts) > 2:
    return match + ' rupees' # unexpected format
  rupees = int(parts[0]) if parts[0] else 0
  paise = int(parts[1]) if len(parts) > 1 and parts[1] else 0
  if rupees and paise:
    rupee_unit = 'rupee' if rupees == 1 else 'rupees'
    paise_unit = 'paisa' if paise == 1 else 'paise'
    return "%s %s, %s %s" % (rupees, rupee_unit, paise, paise_unit)
  elif rupees:
    rupee_unit = 'rupee' if rupees == 1 else 'rupees'
    return '%s %s' % (rupee_unit, rupees)
  elif paise:
    paise_unit = 'paisa' if paise == 1 else 'paise'
    return '%s %s' % (paise, paise_unit)
  else:
    return 'zero rupees' 
  
def _expand_currency_generic(m):
  symbol = m.group(2) or m.group(3)
  number = m.group(1) or m.group(4)
  return '%s %s' % (number, _currency_mapping.get(symbol, symbol))
  
def remove_emoji(text):
  text = re.sub(_emoji_pattern, r'', text)
  text = re.sub(_emoticon_pattern, '', text)
  return text
  
def _expand_units(m):
  number = m.group(1)
  unit = m.group(2)
  if unit == "ft":
    expanded = f"{number} feet"
  elif unit == "in":
    expanded = f"{number} inches"
  elif unit == "cm":
    expanded = f"{number} centimeters"
  elif unit == "m":
    expanded = f"{number} meters"
  elif unit == "km":
    expanded = f"{number} kilometers"
  else:
    expanded = f"{number} {unit}"
    
  return expanded

def _expand_ordinal(m):
  return _inflect.number_to_words(m.group(0))


def _expand_number(m):
  num = int(m.group(0))
  if num > 1000 and num < 3000:
    if num == 2000:
      return 'two thousand'
    elif num > 2000 and num < 2010:
      return 'two thousand ' + _inflect.number_to_words(num % 100)
    elif num % 100 == 0:
      return _inflect.number_to_words(num // 100) + ' hundred'
    else:
      return _inflect.number_to_words(num, andword='', zero='oh', group=2).replace(', ', ' ').replace("-", " ")
  else:
    return _inflect.number_to_words(num, andword='')
  
def replace_math_symbols(text):
  # adding extra space before and after to make sure 2 words arent merged
  # more than one space will be cleared at the end
  text = _math_symbols_pattern.sub(lambda x: " " + _math_symbols[x.group(0)] + " ", text)
  return text

def replace_pronoun(match):
  return _pronoun_list.get(match.group(0).lower(), match.group(0))

def normalize_numbers(text):
  text = re.sub(_comma_number_re, _remove_commas, text)
  text = re.sub(_pounds_re, r'\1 pounds', text)
  text = re.sub(_dollars_re, _expand_dollars, text)
  text = re.sub(_rupees_re, _expand_rupees, text)
  text = re.sub(_currency_pattern_generic, _expand_currency_generic, text)
  text = re.sub(_units_re, _expand_units, text)
  #text = re.sub(_percent_re, r'\1 percents', text)
  # text = text.replace("%", " percent ")
  text = re.sub(_decimal_number_re, _expand_decimal_point, text)
  text = re.sub(_ordinal_re, _expand_ordinal, text)
  text = re.sub(_number_re, _expand_number, text)
  return text


def expand_numbers(text):
  return normalize_numbers(text)


def lowercase(text):
  return text.lower()


def collapse_whitespace(text):
  return re.sub(_whitespace_re, ' ', text)


def convert_to_ascii(text):
  return unidecode(text)

# def separate_capital_letters(text):
#   text = re.sub(r'\b[A-Z]+\b', lambda match: ' '.join(match.group(0)), text)
#   return text

# def initialism(text):
#   words = text.split(" ")
#   spaced_words = []
#   for word in words:
#     # check word after removing punctuations from it for abbreviation
#     if word.translate(_punct_remove_trnslt) in _intialisms:
#       spaced_words.append(' '.join(list(word)))
#     else:
#       spaced_words.append(word)
      
#   return ' '.join(spaced_words)

# def acronyms(text):
#   words = text.split(" ")
#   spaced_words = []
  
#   for word in words:
#     # check word after removing punctuations from it for abbreviation
#     if word.translate(_punct_remove_trnslt) in _acronyms:
#       spaced_words.append(_acronyms[word.translate(_punct_remove_trnslt)])
#     else:
#       spaced_words.append(word)
      
#   return ' '.join(spaced_words)

def contains_alpha_and_numbers(input_str):
    return bool(re.search(r'[a-zA-Z]', input_str)) and bool(re.search(r'\d', input_str))
  
def parse_urls(text):
  pass

def separate_alphanum_word(text):
  '''
  Separate continous segments of alphabets and numbers with space within a word
  CY23 -> CY 23
  K50 -> K 50
  '''
  words = text.split(" ")
  
  spaced_words = []
  for word in words:
    if contains_alpha_and_numbers(word):
      split_words = []
      last_word = word[0]
      last_char_isdigit = word[0].isdigit()
      for char in word[1:]:
        if char.isdigit() == last_char_isdigit:
          last_word += char
        else:
          last_char_isdigit = char.isdigit()
          split_words.append(last_word)
          last_word = char
      split_words.append(last_word)
      word = " ".join(split_words)
    
    spaced_words.append(word)
    
  return " ".join(spaced_words)

def parse_url_for_tts(text):
    parsed_segments = []
    for segment in text.split(" "):
      if is_url(segment):
        # print(segment, urlparse(segment))
        parsed_url = urlparse(segment)
        netloc = " dot ".join(parsed_url.netloc.split("."))
        path = " slash ".join(parsed_url.path.split("/"))
        queries = parsed_url.query.split("&")
        query_pronounce = []
        for query in queries:
          if query:
              key, value = query.split("=")
              if not key in _eng_words_dict:
                key = " ".join(list(key))
              if not value in _eng_words_dict:
                value = " ".join(list(value))
              query_pronounce.append(f"{key} equal {value}")
        queries = " ampersand ".join(query_pronounce)
        url_scheme = parsed_url.scheme
        url_pronounce = [url_scheme, netloc, path, queries]
        url_pronounce = ' slash '.join(url_pronounce)
        segment = url_pronounce
            
      parsed_segments.append(segment)
    
    text = ' '.join(parsed_segments)       
    return text     

def get_initialism(word, append_end_char=''):
  if append_end_char:
    return ' '.join(list(word)) + append_end_char
  else:
    return ' '.join(list(word))

def check_abbreviations(text,abbrasive_words):
  words = text.split(" ")
  spaced_words = []
  
  # Filter out words from abbrasive_words that are present in _acronyms or _intialisms or _eng_words_dict
  filtered_abbrasive_words = [word for word in abbrasive_words if word not in _acronyms and word not in _intialisms and word not in _eng_words_dict]
  
  for word in words:
    # remove apostrophe's if exists at end
    append_end_char = ''
    if word.endswith("'s"):
      word = word[:-2]
      append_end_char = "'s"
    # if abbreivation has 's' at the end to indiciate plural form
    # remove it
    # eg: "While 386 and 398 AQIs were recorded in the Delhi University areas."
    elif word.isalpha() and word[-1] == 's' and word[:-1].isupper():
      word = word[:-1]
      append_end_char = "s"
      
    punct_removed_word = word.translate(_punct_remove_trnslt)

    if punct_removed_word in _acronyms:
      spaced_words.append(_acronyms[punct_removed_word])
    elif punct_removed_word in _intialisms:
      spaced_words.append(get_initialism(punct_removed_word, append_end_char))
    elif punct_removed_word in filtered_abbrasive_words:
      spaced_words.append(get_initialism(punct_removed_word, append_end_char))
    # if word contains only capital letter and not in english dictionary,
    # treat it as initialism and separate each letter by space
    elif punct_removed_word.isupper() and (not punct_removed_word.lower() in _eng_words_dict):
      spaced_words.append(get_initialism(punct_removed_word, append_end_char))
    else:
      spaced_words.append(word + append_end_char)
      
  return ' '.join(spaced_words)

def basic_cleaners(text):
  '''Basic pipeline that lowercases and collapses whitespace without transliteration.'''
  text = lowercase(text)
  text = collapse_whitespace(text)
  return text


def transliteration_cleaners(text):
  '''Pipeline for non-English text that transliterate to ASCII.'''
  text = convert_to_ascii(text)
  text = lowercase(text)
  text = collapse_whitespace(text)
  return text


def english_cleaners(text):
  '''Pipeline for English text, including number and abbreviation expansion.'''
  text = parse_url_for_tts(text)
  text = separate_alphanum_word(text)
  text = expand_numbers(text)
  text = text.replace("...", ". ")
  text = replace_math_symbols(text)
  text = remove_emoji(text)
  text = convert_to_ascii(text)
  # replace pronoun with custom pronunciation
  text = _pronoun_re.sub(replace_pronoun, text)
  #text = separate_capital_letters(text)
  # text = lowercase(text)
  # text = expand_numbers(text)
  # text = expand_abbreviations(text)
  text = collapse_whitespace(text)
  text = text.replace('"', '')
  return text

def nemo_post_processing(text,abbrasive_words):
  # replace initialisms with spaced words
  #text = initialism(text)
  # replace acronyms with pronunciations
  #text = acronyms(text)
  text = check_abbreviations(text,abbrasive_words)
  text = expand_abbreviations(text)
  # replace colons with colon word separated by single space
  text = text.replace(":", " colon ")
  # replace dot inside a word with "point"
  text = re.sub(_replace_dot_in_words, " point ", text)
  # remove extra spaces and only keep a single
  text = collapse_whitespace(text)
  # replace all text into lowercase
  text = lowercase(text)
  return text

def lev_distance(s1, s2):
  if len(s1) > len(s2):
    s1, s2 = s2, s1

  distances = range(len(s1) + 1)
  for i2, c2 in enumerate(s2):
    distances_ = [i2 + 1]
    for i1, c1 in enumerate(s1):
      if c1 == c2:
        distances_.append(distances[i1])
      else:
        distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
    distances = distances_
  return distances[-1]


DEFAULT_VOCAB_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../data/tokenizer.json')


class VoiceBpeTokenizer:
    def __init__(self, vocab_file=None, use_basic_cleaners=False):
        self.tokenizer = Tokenizer.from_file(
          DEFAULT_VOCAB_FILE if vocab_file is None else vocab_file
        )
        if use_basic_cleaners:
            self.preprocess_text = basic_cleaners
        else:
            self.preprocess_text = english_cleaners
        self.nemo_postprocessing_text = nemo_post_processing
        if NEMO:
          self.nemo_model = nemo_model(NEMO_CONFIG_PATH)
        if ROBERTA:
          self.roberta_model = pipeline("token-classification", model="surrey-nlp/roberta-large-finetuned-abbr")
          

    def encode(self, txt):
        # print("Before processing: ", txt.encode("utf-8"))
        txt = self.preprocess_text(txt)
        if NEMO:
            txt = nemo_infer(txt, self.nemo_model)    ## text normalisation
        if ROBERTA:
          abbrasive_words = get_abbreviation(self.roberta_model,txt)   ## RoBERTa model for getting abbreviations in text
        else:
          abbrasive_words = []
        txt = self.nemo_postprocessing_text(txt,abbrasive_words)
        txt = txt.replace(' ', '[SPACE]')
        return self.tokenizer.encode(txt).ids

    def decode(self, seq):
        if isinstance(seq, torch.Tensor):
            seq = seq.cpu().numpy()
        txt = self.tokenizer.decode(seq, skip_special_tokens=False).replace(' ', '')
        txt = txt.replace('[SPACE]', ' ')
        txt = txt.replace('[STOP]', '')
        txt = txt.replace('[UNK]', '')
        return txt
