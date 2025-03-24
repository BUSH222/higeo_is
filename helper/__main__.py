from .db.initialise_database import create_tables, create_database

if input("Creating database, y to continue: ") == 'y':
    create_database()

if input("Creating tables, y to continue: ") == 'y':
    create_tables()

print('Done creating tables!')
