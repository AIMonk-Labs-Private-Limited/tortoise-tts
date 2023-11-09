import csv
import requests
from collections import OrderedDict

from bs4 import BeautifulSoup 

HOME_URL_1 = "https://www.lib.berkeley.edu/EART/abbrev.html"
HOME_URL_2 = "https://www.lib.berkeley.edu/EART/abbrev2.html"
HEADERS = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246"}
OUTPUT = "international_acronyms.csv"

# letters_1 = [chr(c) for c in range(ord('a'), ord('l'))]
# letters_2 = [chr(c) for c in range(ord('l'), ord('x')+1)]

def get_page_acronyms(url):
    print(f"Getting acronyms from {url}...")
    acronyms = {}
    
    page = requests.get(url=url, headers=HEADERS)
    # get page content and parse with bs4
    page = requests.get(url=url, headers=HEADERS)
    soup = BeautifulSoup(page.content, 'html5lib')
    # find all table elements in page, and we get the one for letter provided
    # as arg, and ignore others. Doing this for consistency.
    all_tables = soup.find_all('table')
    
    for table in all_tables:
        for row in table.find_all("tr"):
            columns = row.find_all("td")
            if not len(columns) == 2:
                print("!!WARN: Row found with unknown table format: ", str(row))
                continue
            acronym, full_form = columns[0].get_text(), columns[1].get_text()
            acronyms[acronym.strip()] = full_form.strip()
            
    return acronyms

# def get_letter_table(all_tables, letter):
#     for index, table in enumerate(all_tables):
#         first_row = table.find_all("tr")[0].get_text()
#         if first_row.lower().startswith(letter.lower()):
#             return index
#     return -1

# def get_letter_acronyms(letter, home_url):
#     acronyms = {}
#     url = home_url + '#' + letter
    
#     # get page content and parse with bs4
#     page = requests.get(url=url, headers=HEADERS)
#     soup = BeautifulSoup(page.content, 'html5lib')
#     # find all table elements in page, and we get the one for letter provided
#     # as arg, and ignore others. Doing this for consistency.
#     all_tables = soup.find_all('table')
#     letter_table_index = get_letter_table(all_tables, letter)
    
#     if letter_table_index < 0:
#         print(f"!!WARN: No table found for letter {letter}. Skipping it.")
#         return acronyms
    
#     letter_table = all_tables[letter_table_index]
    
#     for row in letter_table.find_all("tr"):
#         columns = row.find_all("td")
#         if not len(columns) == 2:
#             print("!!WARN: Row found with unknown table format: ", str(row))
#             continue
#         acronym, full_form = columns[0].get_text(), columns[1].get_text()
#         acronyms[acronym.strip()] = full_form.strip()
    
#     return acronyms

def main():
    acronyms = {}
    # for letter in letters_1:
    #     print(f"Getting acronyms for {letter}...\n")
    #     letter_acronyms = get_letter_acronyms(letter, HOME_URL_1)
    #     acronyms.update(letter_acronyms)
    #     print("\n\n")
    
    # for letter in letters_2:
    #     print(f"Getting acronyms for {letter}...\n")
    #     letter_acronyms = get_letter_acronyms(letter, HOME_URL_2)
    #     acronyms.update(letter_acronyms)
    #     print("\n\n")
    
    page1_acronyms = get_page_acronyms(HOME_URL_1)
    page2_acronyms = get_page_acronyms(HOME_URL_2)
    
    acronyms.update(page1_acronyms)
    acronyms.update(page2_acronyms)
    
    acronyms = OrderedDict(sorted(acronyms.items()))
    with open(OUTPUT, 'w') as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(['acronym', 'full-form'])
        
        data = list(zip(list(acronyms.keys()), list(acronyms.values())))
        csvwriter.writerows(data)

if __name__ == '__main__':
    main()