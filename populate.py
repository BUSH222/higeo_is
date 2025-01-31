import psycopg2
import logging
import os
from settings import DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, DATABASE_HOST

conn = psycopg2.connect(dbname=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST)
conn.autocommit = True
cursor = conn.cursor()

with open(os.path.join(os.path.dirname(__file__), 'populate.sql')) as queryfile:
    cursor.execute(queryfile.read())
    conn.commit()
    logging.warning('Tables populated with dummy data')

cursor.close()
conn.close()
