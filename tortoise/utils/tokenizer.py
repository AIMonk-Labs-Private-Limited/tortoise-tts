import os
import re
import json

import inflect
import torch
from tokenizers import Tokenizer


# Regular expression matching whitespace:
from unidecode import unidecode

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

_capitalization_list = [
  'IOC', 'USD', 'CEO', 'DJ', 'US', 'RBI', 'UTC'
]


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
      return _inflect.number_to_words(num, andword='', zero='oh', group=2).replace(', ', ' ')
  else:
    return _inflect.number_to_words(num, andword='')


def normalize_numbers(text):
  text = re.sub(_comma_number_re, _remove_commas, text)
  text = re.sub(_pounds_re, r'\1 pounds', text)
  text = re.sub(_dollars_re, _expand_dollars, text)
  text = re.sub(_rupees_re, _expand_rupees, text)
  text = re.sub(_units_re, _expand_units, text)
  #text = re.sub(_percent_re, r'\1 percents', text)
  text = text.replace("%", " percent ")
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

def separate_capital_letters(text):
  words = text.split(" ")
  spaced_words = []
  
  for word in words:
    if word in _capitalization_list:
      spaced_words.append(' '.join(list(word)))
    else:
      spaced_words.append(word)
      
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
  text = expand_numbers(text)
  text = remove_emoji(text)
  text = convert_to_ascii(text)
  text = separate_capital_letters(text)
  text = lowercase(text)
  # text = expand_numbers(text)
  text = expand_abbreviations(text)
  text = collapse_whitespace(text)
  text = text.replace('"', '')
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

    def encode(self, txt):
        # print("Before processing: ", txt.encode("utf-8"))
        txt = self.preprocess_text(txt)
        # print("After processing: ", txt)
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
