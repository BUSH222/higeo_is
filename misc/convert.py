from sqlalchemy import create_engine
import psycopg2
import csv
import re
from transliterate import get_translit_function
from datetime import datetime
import sys
import zipfile
import os
import io
from dotenv import load_dotenv

csv.field_size_limit(sys.maxsize)

translit_ru = get_translit_function('ru')
load_dotenv()

postgres_connection_string = (
    f"postgresql://{os.getenv('DATABASE_USER')}:"
    f"{os.getenv('DATABASE_PASSWORD')}@"
    f"{os.getenv('DATABASE_HOST')}:"
    f"{os.getenv('DATABASE_PORT')}/"
    f"{os.getenv('DATABASE_NAME')}"
)
engine = create_engine(postgres_connection_string)
zip_file_path = os.path.join(os.path.dirname(__file__), 'data.zip')
conn = psycopg2.connect(postgres_connection_string)
cur = conn.cursor()


def load_sources():
    """
    Load sources from a zip file containing a CSV file.
    The function reads a CSV file named 'source.csv' from a specified zip file,
    and returns a dictionary where the keys are integers from the first column
    of the CSV, and the values are strings from the second column.
    Returns:
        dict: A dictionary with integer keys and string values representing the sources.
    """
    sources = {}
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('source.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                sources[int(row[0])] = row[1]
    return sources


def insert_data(table, columns, values):
    """
    Inserts data into a specified table in the database.
    Args:
        table (str): The name of the table where data will be inserted.
        columns (list): A list of column names where data will be inserted.
        values (list): A list of values corresponding to the columns.
    Returns:
        None
    """
    columns = list(columns)
    values = list(values)
    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))})"
    cur.execute(query, values)


def clean_name(name):
    """
    Cleans the input name string by removing unwanted characters and normalizing spaces.
    This function performs the following operations:
    1. Removes square brackets [] and parentheses ().
    2. Retains only alphabetic characters, spaces, and hyphens.
    3. Replaces multiple spaces with a single space.
    4. Strips leading and trailing whitespace.
    Args:
        name (str): The input name string to be cleaned.
    Returns:
        str: The cleaned name string.
    """
    name = re.sub(r'[\[\]\(\)]', '', name)
    name = ''.join(e for e in name if e.isalpha() or e.isspace() or e == '-')
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    return name


def get_new_person_id(old_person_id):
    """
    Retrieve the new person ID based on the old person ID.
    Args:
        old_person_id (int): The old person ID to look up.
    Returns:
        int or None: The new person ID if found, otherwise None.
    """
    query = "SELECT id FROM person WHERE _oldid = %s"
    cur.execute(query, (old_person_id,))
    result = cur.fetchone()
    return result[0] if result else None


def get_new_document_id(old_document_id):
    """
    Retrieve the new document ID based on the old document ID.
    This function executes a SQL query to fetch the new document ID from the
    'document' table where the '_oldid' matches the provided old_document_id.
    Args:
        old_document_id (int): The old document ID to search for.
    Returns:
        int or None: The new document ID if found, otherwise None.
    """
    query = "SELECT id FROM document WHERE _oldid = %s"
    cur.execute(query, (old_document_id,))
    result = cur.fetchone()
    return result[0] if result else None


def get_new_org_id(old_org_id):
    """
    Retrieve the new organization ID based on the old organization ID.
    Args:
        old_org_id (int): The old organization ID to look up.
    Returns:
        int or None: The new organization ID if found, otherwise None.
    """
    query = "SELECT id FROM organization WHERE _oldid = %s"
    cur.execute(query, (old_org_id,))
    result = cur.fetchone()
    return result[0] if result else None


def clean_date(date_str):
    """
    Cleans and converts a given date string into a standardized datetime object.
    The function attempts to match the input date string against several predefined patterns
    and special cases. If a match is found, it converts the date string into a datetime object.
    If no match is found, it returns None and the original date string.
    Args:
        date_str (str): The date string to be cleaned and converted.
    Returns:
        tuple: A tuple containing:
            - datetime or None: The converted datetime object if a match is found, otherwise None.
            - str or None: The original date string if no match is found, otherwise None.
    """
    patterns = [
        (r'^\s*(\d{4})\s*,\s*(\d{1,2})\s*('
         r'января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|'
         r'январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|'
         r'дкабря|нояб.|агуста|июн)\s*$', '%Y, %d %B'),
        (r'^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$', '%Y-%m-%d'),
        (r'^\s*(\d{4})\s*г\.\s*,\s*(\d{1,2})\s*('
         r'января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|'
         r'январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|'
         r'дкабря|нояб.|агуста|июн)\s*$', '%Y г., %d %B'),
        (r'^\s*(\d{1,2})\s*апр\.\s*(\d{4})\s*$', '%d апр. %Y'),
        (r'^\s*(\d{4})\.\s*(\d{1,2})\s*мая\s*$', '%Y. %d мая'),
        (r'^\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*$', '%d-%m-%Y')
    ]
    special_cases = {
        '1968, 31января ': '1968-01-31',
        '25, ноябрь 1927': '1927-11-25',
        '1896, 19 февр.': '1896-02-19',
        '1934. 29 июля': '1934-07-29',
        '1948, 28 янв.': '1948-01-28',
        '1939, 2 апреля.': '1939-04-02',
        '19 ноября 1883 г.': '1883-11-19',
        '1941, 16.июля': '1941-07-16',
        '13 сентября 1909': '1909-09-13',
        '1883 г  3 апреля': '1883-04-03',
        '1903 г. 26 декабря': '1903-12-26',
        '1959 25 июня': '1959-06-25',
        '1915 26 июля': '1915-07-26',
        '1940, 17 феврал': '1940-02-17',
        '29 июня 1976': '1976-06-29',
        '1947 , 7 марта': '1947-03-07',
        '1948 3, мая': '1948-05-03',
        '1969, 1 мая.': '1969-05-01',
        '1956 11, сентября': '1956-09-11',
        '10, марта 2013': '2013-03-10',
        '2017. 25 июня': '2017-06-25',
        '19 февраля 1956 г.': '1956-02-19',
        '14 мая 2006': '2006-05-14',
        '17 февраля 2005': '2005-02-17',
        '2004 , 20 августа ': '2004-08-20',
        '1990, 23 августа 199': '1990-08-23',
        '2005. 15 февраля': '2005-02-15'
    }
    if date_str in special_cases:
        return datetime.strptime(special_cases[date_str], '%Y-%m-%d'), None

    for pattern, date_format in patterns:
        match = re.match(pattern, date_str)
        if match:
            try:
                month_map = {
                    'января': 'January', 'февраля': 'February', 'марта': 'March', 'апреля': 'April',
                    'мая': 'May', 'июня': 'June', 'июля': 'July', 'августа': 'August',
                    'сентября': 'September', 'октября': 'October', 'ноября': 'November', 'декабря': 'December',
                    'январь': 'January', 'февраль': 'February', 'март': 'March', 'апрель': 'April',
                    'май': 'May', 'июнь': 'June', 'июль': 'July', 'август': 'August',
                    'сентябрь': 'September', 'октябрь': 'October', 'ноябрь': 'November', 'декабрь': 'December',
                    'дкабря': 'December', 'нояб.': 'November', 'агуста': 'August', 'июн': 'June'
                }
                date_str = re.sub('|'.join(month_map.keys()), lambda m: month_map[m.group(0)], date_str)
                return datetime.strptime(date_str, date_format), None
            except ValueError:
                continue

    return None, date_str


def convert_person():
    """
    Extracts and processes person data from a zipped CSV file, then inserts the processed data into a database.
    The function reads a CSV file named 'person.csv' from a specified zip file. It processes each row to extract
    and clean various fields related to a person, such as name, surname, patronymic, birth date, death date, etc.
    It also handles transliteration of the patronymic and formats comments based on the presence of birth and death
    dates.
    Finally, it inserts the cleaned and processed data into a database table named 'person'.
    Raises:
        FileNotFoundError: If the zip file or the CSV file within the zip does not exist.
        KeyError: If the expected columns are not found in the CSV file.
        ValueError: If there are issues with data conversion or insertion.
    """
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('person.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                comment = row[21]

                patronymic = row[5]
                patronymic_en = translit_ru(patronymic, reversed=True)

                birth_date, birth_date_str = clean_date(row[10])
                death_date, death_date_str = clean_date(row[12])
                if birth_date is None and birth_date_str is not None:
                    comment += f'Дата рождения: {birth_date_str}. '
                if death_date is None and death_date_str is not None:
                    comment += f'Дата смерти: {death_date_str}. '

                surname = row[6]
                if surname is None or surname == '':
                    surname = row[1].strip().split()[0]

                photo = row[20]
                if photo is not None:
                    if photo.startswith('/higeo/hosted-files') or photo.startswith('/hosted-files'):
                        photo = 'http://higeo.ginras.ru' + photo

                data = {
                    '_oldid': int(row[0]),
                    'name': clean_name(row[4]),
                    'surname': clean_name(surname),
                    'patronymic': patronymic,
                    'name_en': clean_name(row[7]),
                    'surname_en': clean_name(row[8]),
                    'patronymic_en': patronymic_en,
                    'birth_date': birth_date,
                    'birth_place': row[11],
                    'death_date': death_date,
                    'death_place': row[13],
                    'academic_degree': row[14],
                    'field_of_study': row[15],
                    'area_of_study': row[16],
                    'biography': row[18],
                    'bibliography': row[19],
                    'photo': photo,
                    'comment': comment
                }
                data = {k: (v if v != '' else None) for k, v in data.items()}

                insert_data('person', data.keys(), data.values())


def convert_org():
    """
    Reads data from a CSV file within a ZIP archive and inserts it into the 'organization' table.
    The function performs the following steps:
    1. Opens a ZIP file specified by `zip_file_path`.
    2. Reads the 'org.csv' file from the ZIP archive.
    3. Parses the CSV file and extracts relevant data from each row.
    4. Maps the extracted data to a dictionary with specific keys.
    5. Replaces empty string values with None.
    6. Inserts the data into the 'organization' table using the `insert_data` function.
    The CSV file is expected to have the following columns:
    - Column 0: Old ID (converted to integer)
    - Column 1: Name
    - Column 4: Organization type
    - Column 5: History
    - Column 7: Comment
    Note:
    - The `zip_file_path` variable should be defined and point to the ZIP file location.
    - The `insert_data` function should be defined to handle the insertion of data into the database.
    Raises:
    - Any exceptions raised by the `zipfile.ZipFile`, `csv.reader`, or `insert_data` functions.
    """
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('org.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:

                data = {
                    '_oldid': int(row[0]),
                    'name': row[1],
                    'org_type': row[4],
                    'history': row[5],
                    'comment': row[7]
                }
                data = {k: (v if v != '' else None) for k, v in data.items()}

                insert_data('organization', data.keys(), data.values())


def convert_doc():
    """
    Converts and inserts document data from a zipped CSV file into a database.
    This function performs the following steps:
    1. Loads source data from an external source.
    2. Reads a CSV file named 'pub.csv' from a specified zip file.
    3. Iterates through each row in the CSV file and extracts relevant data.
    4. Maps the source ID to the corresponding source text.
    5. Constructs a dictionary with the extracted data, replacing empty strings with None.
    6. Inserts the constructed data into the 'document' table in the database.
    Note:
        The function assumes the existence of the following:
        - `load_sources()`: A function that loads and returns a dictionary of source data.
        - `zip_file_path`: A variable containing the path to the zip file.
        - `insert_data(table, keys, values)`: A function that inserts data into the specified table.
    Raises:
        KeyError: If the source ID is not found in the sources dictionary.
        ValueError: If any of the data conversion (e.g., int) fails.
    """
    sources_dict = load_sources()

    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('pub.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                source_id = int(row[1])
                source_text = sources_dict.get(source_id, None)

                data = {
                    '_oldid': int(row[0]),
                    'name': row[2],
                    'doc_type': row[4],
                    'language': row[5],
                    'source': source_text,
                    'year': row[6],
                    'comment': row[8]
                }
                data = {k: (v if v != '' else None) for k, v in data.items()}

                insert_data('document', data.keys(), data.values())


def convert_document_authorship():
    """
    Converts document authorship data from a CSV file within a ZIP archive.
    This function reads a CSV file named 'author.csv' from a specified ZIP file,
    processes each row to map old document and person IDs to new IDs, and
    inserts the converted data into the 'document_authorship' table.
    The CSV file is expected to have the following columns:
    - Column 0: Old document ID (integer)
    - Column 1: Old person ID (integer)
    The function performs the following steps:
    1. Opens the ZIP file specified by `zip_file_path`.
    2. Reads the 'author.csv' file from the ZIP archive.
    3. Iterates over each row in the CSV file.
    4. Converts old document and person IDs to new IDs using `get_new_document_id` and `get_new_person_id`.
    5. If both new IDs are valid, inserts the data into the 'document_authorship' table.
    Note:
    - The `zip_file_path` variable should be defined and point to the ZIP file location.
    - The `get_new_document_id` and `get_new_person_id` functions should be implemented to return the new IDs.
    - The `insert_data` function should be implemented to handle the database insertion.
    """
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('author.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                old_document_id = int(row[0])
                old_person_id = int(row[1])

                new_person_id = get_new_person_id(old_person_id)
                new_document_id = get_new_document_id(old_document_id)

                if new_person_id and new_document_id:
                    data = {
                        'document_id': new_document_id,
                        'person_id': new_person_id
                    }
                    insert_data('document_authorship', data.keys(), data.values())


def convert_organization_membership():
    """
    Converts organization membership data from a CSV file within a ZIP archive.
    This function reads a CSV file named 'employ.csv' from a specified ZIP file,
    processes each row to map old person and organization IDs to new IDs, and
    inserts the converted data into the 'organization_membership' table.
    The CSV file is expected to have the following columns:
    - Column 0: Old person ID (integer)
    - Column 1: Old organization ID (integer)
    The function performs the following steps:
    1. Opens the ZIP file specified by `zip_file_path`.
    2. Reads the 'employ.csv' file from the ZIP archive.
    3. Iterates over each row in the CSV file.
    4. Converts old person and organization IDs to new IDs using `get_new_person_id` and `get_new_org_id`.
    5. If both new IDs are valid, inserts the data into the 'organization_membership' table.
    Note:
    - The `zip_file_path` variable should be defined and point to the ZIP file location.
    - The `get_new_person_id` and `get_new_org_id` functions should be implemented to return the new IDs.
    - The `insert_data` function should be implemented to handle the database insertion.
    """

    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('employ.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                old_person_id = int(row[0])
                old_org_id = int(row[1])

                new_person_id = get_new_person_id(old_person_id)
                new_org_id = get_new_org_id(old_org_id)

                if new_person_id and new_org_id:
                    data = {
                        'person_id': new_person_id,
                        'organization_id': new_org_id
                    }
                    insert_data('organization_membership', data.keys(), data.values())


if __name__ == '__main__':
    assert input('proceed with data conversion? (y/n) ') == 'y'
    cur.execute("TRUNCATE TABLE person CASCADE")
    cur.execute("TRUNCATE TABLE organization CASCADE")
    cur.execute("TRUNCATE TABLE document CASCADE")
    cur.execute("TRUNCATE TABLE organization_membership CASCADE")
    cur.execute("TRUNCATE TABLE document_authorship CASCADE")
    conn.commit()
    convert_person()
    convert_org()
    convert_doc()
    conn.commit()
    convert_document_authorship()
    convert_organization_membership()
    conn.commit()
    print("Data has been successfully imported and transformed.")
cur.close()
conn.close()
engine.dispose()
