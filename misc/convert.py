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

csv.field_size_limit(sys.maxsize)

translit_ru = get_translit_function('ru')
postgres_connection_string = 'postgresql://postgres:12345678@localhost:5432/geology'
engine = create_engine(postgres_connection_string)
zip_file_path = os.path.join(os.path.dirname(__file__), 'data.zip')
conn = psycopg2.connect(postgres_connection_string)
cur = conn.cursor()


def load_sources():
    sources = {}
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('source.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                sources[int(row[0])] = row[1]
    return sources


def insert_data(table, columns, values):
    columns = list(columns)
    values = list(values)
    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))})"
    cur.execute(query, values)


def clean_name(name):
    name = re.sub(r'[\[\]\(\)]', '', name)
    name = ''.join(e for e in name if e.isalpha() or e.isspace() or e == '-')
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    return name


def get_new_person_id(old_person_id):
    query = "SELECT id FROM person WHERE _oldid = %s"
    cur.execute(query, (old_person_id,))
    result = cur.fetchone()
    return result[0] if result else None


def get_new_document_id(old_document_id):
    query = "SELECT id FROM document WHERE _oldid = %s"
    cur.execute(query, (old_document_id,))
    result = cur.fetchone()
    return result[0] if result else None


def get_new_org_id(old_org_id):
    query = "SELECT id FROM organization WHERE _oldid = %s"
    cur.execute(query, (old_org_id,))
    result = cur.fetchone()
    return result[0] if result else None


def clean_date(date_str):
    patterns = [
        (r'^\s*(\d{4})\s*,\s*(\d{1,2})\s*('
         r'января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|'
         r'январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь|'
         r'дкабря|нояб.|агуста|июн)\s*$', '%Y, %d %B'),
        (r'^\s*(\d{4})-(\d{2})-(\d{2})\s*$', '%Y-%m-%d'),
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
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('person.csv') as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            for row in reader:
                comment = row[21]

                patronymic = row[5]
                patronymic_en = translit_ru(patronymic, reversed=True)

                birth_date, birth_date_str = clean_date(row[10])
                death_date, death_date_str = clean_date(row[12])

                if birth_date is None:
                    comment += f'\n Birth date: {birth_date_str}'

                if death_date is None:
                    comment += f'\n Death date: {birth_date_str}'

                surname = row[6]
                if surname is None or surname == '':
                    surname = row[1].strip().split()[0]

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
                    'photo': row[20],
                    'comment': comment
                }
                data = {k: (v if v != '' else None) for k, v in data.items()}

                insert_data('person', data.keys(), data.values())


def convert_org():
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
    assert input('proceed? (y/n) ') == 'y'
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
