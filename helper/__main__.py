from .db.populate import populate
from .db.initialise_database import create_tables

if input("Creating tables, y to continue: ") == 'y':
    create_tables()
else:
    print('Aborting')


if input("Populating the table with dummy data, y to continue: ") == 'y':
    populate()
else:
    print('Aborting')

print('Done!')
