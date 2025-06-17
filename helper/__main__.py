from .db.initialise_database import create_tables, create_database, drop_tables

if input("Creating database, y to continue: ") == 'y':
    create_database()

if input("Removing old tables, y to continue: ") == 'y':
    drop_tables()

if input("Creating tables, y to continue: ") == 'y':
    create_tables()

print('Done creating tables!')
