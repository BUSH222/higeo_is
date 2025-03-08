import pandas as pd
from sqlalchemy import create_engine
import psycopg2

# Define the connection string for PostgreSQL
postgres_connection_string = 'postgresql://postgres:12345678@localhost:5432/geology'

# Create a SQLAlchemy engine
engine = create_engine(postgres_connection_string)

# Execute the new_structure.sql script to create the new structure
with engine.connect() as connection:
    with open('/Users/tedvtorov/Desktop/py-proj/new/higeo_is/misc/new_structure.sql', 'r') as file:
        sql_script = file.read()
    connection.execute(sql_script)

# Define file paths
csv_files = {
    'author': '/Users/tedvtorov/data/author.csv',
    'employ': '/Users/tedvtorov/data/employ.csv',
    'org': '/Users/tedvtorov/data/org.csv',
    'person': '/Users/tedvtorov/data/person.csv',
    'pub': '/Users/tedvtorov/data/pub.csv'
}

# Connect to the PostgreSQL database using psycopg2
conn = psycopg2.connect(postgres_connection_string)
cur = conn.cursor()


def insert_data(table, columns, values):
    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))})"
    cur.execute(query, values)


with open(csv_files['person'], 'r') as file:
    df_person = pd.read_csv(file)
    for index, row in df_person.iterrows():
        row['patronymic_en'] = None  # Set patronymic_en to NULL by default
        columns = ['id', 'name', 'surname', 'patronymic', 'name_en', 'surname_en', 'patronymic_en',
                   'birth_date', 'death_date', 'birth_place', 'death_place', 'academic_degree',
                   'field_of_study', 'area_of_study', 'biography', 'bibliography', 'photo', 'comment']
        values = [row['_id'], row['name'], row['first_name_ru'], row['last_name_ru'], row['middle_name_ru'],
                  row['first_name_en'], row['last_name_en'], row['patronymic_en'], row['birth_date'],
                  row['death_date'], row['birth_country'], row['death_country'], row['degree'],
                  row['geo'], row['int'], row['bio'], row['bib'], row['fot'], row['chl']]
        insert_data('person', columns, values)

# Read and insert organization data
with open(csv_files['org'], 'r') as file:
    df_org = pd.read_csv(file)
    for index, row in df_org.iterrows():
        columns = ['id', 'name', 'comment']
        values = [row['_id'], row['name'], row['chl']]
        insert_data('organization', columns, values)

# Read and insert document data
with open(csv_files['pub'], 'r') as file:
    df_pub = pd.read_csv(file)
    for index, row in df_pub.iterrows():
        row['comment'] = None  # Set comment to NULL by default
        columns = ['id', 'name', 'source', 'year', 'file', 'comment']
        values = [row['_id'], row['name'], row['_source'], row['god'], row['fil'], row['comment']]
        insert_data('document', columns, values)

# Read and insert organization_membership data
with open(csv_files['employ'], 'r') as file:
    df_employ = pd.read_csv(file)
    for index, row in df_employ.iterrows():
        columns = ['person_id', 'organization_id']
        values = [row['person'], row['org']]
        insert_data('organization_membership', columns, values)

# Read and insert document_authorship data
with open(csv_files['author'], 'r') as file:
    df_author = pd.read_csv(file)
    for index, row in df_author.iterrows():
        columns = ['person_id', 'document_id']
        values = [row['person'], row['pub']]
        insert_data('document_authorship', columns, values)

# Commit the transaction and close the connection
conn.commit()
cur.close()
conn.close()

print("Data has been successfully imported and transformed.")
