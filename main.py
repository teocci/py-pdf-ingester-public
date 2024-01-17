import os
import re
import requests
from datetime import datetime
from lxml import html
from pypdf import PdfReader

# Specify the directory where the PDF files are located
pdf_directory = './data'


class Document:
    def __init__(self):
        self.name = ''
        self.filename = ''
        self.pages = 0
        self.booklet_line = 0
        self.content_line = 0
        self.chamber_name_line = 0
        self.case_file_line = 0
        self.first_case_file = True

    def clear(self):
        self.name = ''
        self.pages = 0
        self.booklet_line = 0
        self.content_line = 0
        self.chamber_name_line = 0
        self.case_file_line = 0
        self.first_case_file = True


class Booklet:
    def __init__(self, number, issue_date):
        self.number = number
        self.issue_date = issue_date
        self.chambers = []

    def add_chamber(self, chamber):
        self.chambers.append(chamber)


class Chamber:
    def __init__(self, name, page):
        self.name = name
        self.page = int(page)
        self.title_line = 0
        self.case_files = []

    def add_case_file(self, case_file):
        self.case_files.append(case_file)


class CaseFile:
    def __init__(self, code, page):
        self.code = code
        self.page = int(page)
        self.tag = ''


class CaseFilePart:
    def __init__(self):
        self.same = True
        self.wait = True
        self.fp = ''
        self.sp = ''

    def update(self):
        if self.same:
            self.same = False
        else:
            self.wait = False

    def reset(self):
        self.same = True
        self.wait = True
        self.fp = ''
        self.sp = ''


def download_pdf_files():
    url = "https://diariooficial.elperuano.pe/Casaciones/Filtro?Length=0"
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    payload = {"ddwANO": "2023", "ddwMES": "05"}  # Adjust year and month as needed

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        print("Error: Failed to fetch the data.")
        return

    root = html.fromstring(response.content)
    articles = root.xpath('//article[contains(@class, "normaslegales_articulos")]')

    for article in articles:
        date_string = article.xpath('p[contains(text(), "Fecha:")]/text()')[0].split(":")[1].strip()
        download_link = article.xpath('.//a[@href]/@href')[0]

        file_name = ''
        date_pattern = r'(\d{2})/(\d{2})/(\d{4})'
        date_match = re.search(date_pattern, date_string)
        if date_match:
            day, month, year = date_match.groups()
            file_name = f"CA{year}{month}{day}"

        file_path = f"./data/{file_name}.pdf"

        if os.path.exists(file_path):
            print(f"File {file_name}.pdf already exists. Skipping...")
        else:
            download_url = download_link
            response = requests.get(download_url)

            if response.status_code == 200:
                with open(file_path, "wb") as file:
                    file.write(response.content)
                print(f"File {file_name}.pdf downloaded successfully.")
            else:
                print(f"Failed to download {file_name}.pdf.")


document_info = Document()


def trim_string(string):
    """Trims whitespace and newline characters from a string.

    Args:
      string: The string to trim.

    Returns:
      The trimmed string.
    """

    return re.sub(r'\s+', '', string).strip()


def is_empty(s):
    """Checks if a string is empty.

    Args:
    s: The string to check.

    Returns:
    True if the string is empty, False otherwise.
    """

    return len(s) == 0


def parse_booklet(reader):
    booklet_number = ''

    def parse_booklet_number(text, cm, tm, font_dict, font_size):
        # if 600 > tm[5] > 560 and not is_empty(trim_string(text)):
        if not is_empty(trim_string(text)):
            nonlocal booklet_number
            # print(f'parse_booklet_number-> text: {text}, tm: {tm}')
            booklet_number_match = re.search(r"Año [A-Z]* / Nº (\d+)", text)
            if booklet_number_match:
                booklet_number = booklet_number_match.group(1)
                document_info.booklet_line = tm[5]

            content_pattern = r'^contenido'
            content_match = re.search(content_pattern, text.lower())
            if content_match:
                document_info.content_line = tm[5]

            case_file_pattern = r'casac(.*?)\sn.\s'
            case_file_match = re.search(case_file_pattern, text.lower())
            # print(f'parse_booklet_number-> text[lower]: {text.lower()}, tm: {tm}')
            if case_file_match and document_info.first_case_file:
                # print(f'case_file_match-> tm: {tm}')
                document_info.case_file_line = tm[5]
                document_info.first_case_file = False

    booklet_page = reader.pages[0]
    booklet_page.extract_text(visitor_text=parse_booklet_number)

    return booklet_number


def find_chamber_tittle_line(reader, booklet):
    for chamber in booklet.chambers:
        def parse_chamber_title(text, cm, tm, font_dict, font_size):
            if not is_empty(trim_string(text)) and chamber.title_line == 0:
                clean_text = text.strip()
                # print(f'parse_chamber_title-> clean_text: {clean_text}')
                if clean_text == chamber.name:
                    chamber.title_line = tm[5]

        # print(f'chamber: {chamber.name}, page: {chamber.page}')
        page_number = int(chamber.page)
        print(
            f'file_name: {document_info.filename}, chamber_name: {chamber.name}, page_number: {page_number}, total_pages: {document_info.pages}')
        chamber_page = reader.pages[page_number - 1]
        chamber_page.extract_text(visitor_text=parse_chamber_title)


def parse_chambers(reader, booklet):
    def parse_chamber_lines(text, cm, tm, font_dict, font_size):
        # print(f'case_file_line: {document_info.case_file_line}, content_line: {document_info.content_line}')
        if document_info.content_line > tm[5] > document_info.case_file_line and not is_empty(trim_string(text)):
            # print(f'parse_chamber_lines-> text: {text}')
            chamber_pattern = r'([A-Z ]+).*?(\d+)'
            chamber_match = re.search(chamber_pattern, text)
            if chamber_match:
                print(f'chamber_match-> text: {text}')
                nc_name = chamber_match.group(1).strip()
                nc_page = chamber_match.group(2)
                new_chamber = Chamber(nc_name, nc_page)
                booklet.add_chamber(new_chamber)
                document_info.chamber_name_line = tm[5]

    booklet_page = reader.pages[0]
    booklet_page.extract_text(visitor_text=parse_chamber_lines)

    find_chamber_tittle_line(reader, booklet)

    # start_match = re.search(start_pattern, first_page_text)
    # end_match = re.search(end_pattern, first_page_text)
    #
    # if start_match and end_match:
    #     start_index = start_match.end()
    #     end_index = end_match.start()
    #     text = first_page_text[start_index:end_index].strip()
    #     lines = re.split(r'\n', text)
    #     for line in lines:
    #         chamber_name = parse_chamber_name(line)
    #         page = parse_chamber_page(line)
    #         chamber = Chamber(chamber_name, page)
    #         booklet.add_chamber(chamber)


def parse_chamber_name(text):
    chamber_name = ""
    match = re.search(r'\.', text)
    if match:
        chamber_name = text[:match.start()]

    return chamber_name


def parse_chamber_page(text):
    page = ""
    match = re.search(r'.*?(\d+)', text)
    if match:
        page = match.group(1)

    return page


def extract_chamber_case_files(reader, chamber):
    case_file_part = CaseFilePart()

    def parse_case_file_line(t):
        # print(f'parse_case_file_line-> text: {text.lower()}')
        text = t.strip().replace('\t', ' ').lower()
        case_file_pattern = r'(casaci.n n. \d+.{1,3}\d{4} [a-zñáéíóú ]+)[. ]*?(\d+)'
        case_file_match = re.search(case_file_pattern, text)
        if case_file_match:
            print(f'case_file_match-> text: {text}')
            case_file_name = case_file_match.group(1).strip()
            case_file_page = case_file_match.group(2)
            new_case_file = CaseFile(case_file_name, case_file_page)
            chamber.add_case_file(new_case_file)
            return
        print(f'parse_case_file_fp_line-> text: {text}')
        case_file_part.update()
        case_file_fp_pattern = r'(casaci.n n. \d+.{1,3}\d{4} [a-zñáéíóú ]+)'
        case_file_fp_match = re.search(case_file_fp_pattern, text)
        if case_file_fp_match:
            print(f'case_file_fp_match-> text: {text}')
            case_file_part.reset()
            case_file_part.fp = case_file_fp_match.group(1).strip()

        if not case_file_part.same and case_file_part.wait:
            case_file_sp_pattern = r'(casaci.n\sn.\s\d+.{1,3}\d{4}\s[a-zñáéíóú ]+)[. \s]*?(\d+)'
            case_file_sp_match = re.search(case_file_sp_pattern, case_file_part.fp.lower() + text.lower())
            if case_file_sp_match:
                print(f'case_file_sp_match-> text: {text}')
                case_file_name = case_file_sp_match.group(1).strip()
                case_file_page = case_file_sp_match.group(2)
                new_case_file = CaseFile(case_file_name, case_file_page)
                chamber.add_case_file(new_case_file)

    def parse_case_file_lines_first_page(text, cm, tm, font_dict, font_size):
        if tm[5] < chamber.title_line and not is_empty(trim_string(text)):
            parse_case_file_line(text)

    def parse_case_file_lines(text, cm, tm, font_dict, font_size):
        if tm[5] < 710 and not is_empty(trim_string(text)):
            parse_case_file_line(text)

    page_number = int(chamber.page)
    chamber_page = reader.pages[page_number - 1]
    chamber_page.extract_text(visitor_text=parse_case_file_lines_first_page)

    start_page = page_number + 1
    end_page = chamber.case_files[0].page

    while start_page <= end_page:
        chamber_page = reader.pages[start_page - 1]
        chamber_page.extract_text(visitor_text=parse_case_file_lines)
        start_page += 1

    # start_page = chamber_page + 1
    # end_page = number_of_pages - 1
    #
    # for page_number in range(start_page, end_page):
    #     page_text = reader.pages[page_number].extract_text()
    #     case_file_matches = re.findall(r"CASACIÓN Nº (\d+-\d{4} [A-Z]+)[\s\S]*?(\d+)", page_text)
    #
    #     for case_file_match in case_file_matches:
    #         case_file_code = case_file_match[0]
    #         case_file_page = case_file_match[1]
    #         tag_match = re.search(fr"{case_file_code}[\s\S]*?SUMILLA:", page_text)
    #         if tag_match:
    #             case_file_tag = "Sentencia"
    #         else:
    #             case_file_tag = "Auto"
    #
    #         case_file = CaseFile(case_file_code, case_file_page, case_file_tag)
    #         chamber.add_case_file(case_file)


def extract_booklet_info(file_path, filename):
    issue_date = None
    line = ""
    case_files = []

    with open(file_path, 'rb') as file:
        reader = PdfReader(file)
        document_info.pages = len(reader.pages)
        number_of_pages = len(reader.pages)

        # Extract issue date
        issue_date_match = re.search(r"(\d{1,2}).(\d{2}).(\d{4}).pdf", filename)

        # Extract booklet number
        booklet_number = parse_booklet(reader)

        if issue_date_match:
            day = issue_date_match.group(1)
            month = issue_date_match.group(2)
            year = issue_date_match.group(3)
            issue_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
            print(f"Issue date: {issue_date}")

        booklet = Booklet(booklet_number, issue_date)

        # Extract chamber names
        parse_chambers(reader, booklet)

        for chamber in booklet.chambers:
            print(f"Chamber: {chamber.name}")
            extract_chamber_case_files(reader, chamber)

        # Extract case files
        index_page = number_of_pages - 1
        index_page_text = reader.pages[index_page].extract_text()
        index_match = re.search(r"Índice\n\n(.+)", index_page_text, re.DOTALL)
        if index_match:
            index_text = index_match.group(1)
            case_file_matches = re.findall(r"CASACIÓN Nº (\d+-\d{4} [A-Z]+)[\s\S]*?(\d+)", index_text)

            for case_file_match in case_file_matches:
                case_file_code = case_file_match[0]
                case_file_page = case_file_match[1]
                tag_match = re.search(fr"{case_file_code}[\s\S]*?SUMILLA:", index_text)
                if tag_match:
                    case_file_tag = "Sentencia"
                else:
                    case_file_tag = "Auto"

                case_file = CaseFile(case_file_code, case_file_page, case_file_tag)
                case_files.append(case_file)

    for chamber in booklet.chambers:
        for case_file in case_files:
            chamber.add_case_file(case_file)

    return booklet


def main():
    download_pdf_files()
    # Iterate over PDF files in the directory
    for filename in os.listdir(pdf_directory):
        if filename.endswith(".pdf"):
            document_info.clear()
            document_info.filename = filename
            file_path = os.path.join(pdf_directory, filename)
            booklet = extract_booklet_info(file_path, filename)

            print(f"Booklet Number: {booklet.number}")
            print(f"Issue Date: {booklet.issue_date}")

            for chamber in booklet.chambers:
                print(f"\nChamber Name: {chamber.name}")
                print(f"Chamber Page: {chamber.page}")

                for case_file in chamber.case_files:
                    print(f"\nCase File Code: {case_file.code}")
                    print(f"Resolution Page: {case_file.page}")
                    print(f"Tag: {case_file.tag}")

            print("-" * 50)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
