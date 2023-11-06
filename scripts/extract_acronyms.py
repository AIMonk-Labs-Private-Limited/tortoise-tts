import re
import csv
import argparse
from collections import OrderedDict

import PyPDF2
from tabula.io import read_pdf

# pattern = r'(\S+)\s+(\S+)'
# def extract_two_columns(text):
#     column1 = []
#     column2 = []

#     matches = re.findall(pattern, text)
#     for match in matches:
#         column1.append(match[0])
#         column2.append(match[1])

#     return column1, column2
# column1, column2 = extract_two_columns(pdf_text)

# tables = read_pdf(
#     pdf_file, 
#     pages=list(range(start_page-1, end_page+1)), 
#     multiple_tables=True,
#     stream=True
# )

pdf_file = "echapter.pdf"
pdf_text = ""

def parse_args():
    parser = argparse.ArgumentParser(description="Extract acronyms from pdf")
    parser.add_argument(
        "-i", "--input", type=str, required=True,
        help="Path to the text file containing pdf file path, start and end page numbers"
    )
    parser.add_argument(
        "-o", "--output", type=str, default="acronyms.csv",
        help="Path to the csv file to save acronyms"
    )
    return parser.parse_args()

def find_start(rows):
    for i, row in enumerate(rows):
        splitted_row = row.strip().split(" ")
        if len(splitted_row) <= 1:
            continue
        else:
            acronym = splitted_row[0]
            fullform = " ".join(splitted_row[1:])
            
            if not acronym.isupper():
                continue
            if fullform.isupper():
                continue
            
        break
    
    return i

def extract_acronym(pdf_file, start_page_no, end_page_no):
    pdf_text = ""
    acronyms = {}
    reader = PyPDF2.PdfReader(pdf_file)

    # get all text from pdf
    for page_num in range(start_page_no-1, end_page_no):
        page = reader.pages[page_num]
        pdf_text += page.extract_text()

    # split text by \n to get each row
    rows = pdf_text.split("\n")
    
    row_start = find_start(rows)

    for row in rows[row_start:]:
        splitted_row = row.strip().split(" ")
        # if space split contains one or less words, skip it
        if len(splitted_row) <= 1:
            continue
        acronym = splitted_row[0]
        if acronym.endswith("-"):
            acronym = acronym[:-1]
        fullform = " ".join(splitted_row[1:])
        acronyms[acronym] = fullform
        
    return acronyms

def extract_acronym_from_html(html_path):
    pass

def main():
    args = parse_args()
    
    with open(args.input, 'r') as f:
        lines = f.readlines()
        
    acronyms = {}
    for line in lines:
        # ignore comments
        if line.startswith('#'):
            continue
        pdf_path, start_page_no, end_page_no = line.split("\t")
        pdf_acronyms = extract_acronym(pdf_path, int(start_page_no), int(end_page_no))
        acronyms.update(pdf_acronyms)
        
    acronyms = OrderedDict(sorted(acronyms.items()))
        
    with open(args.output, 'w') as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(['acronym', 'full-form'])
        
        data = list(zip(list(acronyms.keys()), list(acronyms.values())))
        csvwriter.writerows(data)
        
if __name__ == '__main__':
    main()
