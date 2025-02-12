from .db.populate import populate

if input("Populating the table with dummy data, y to continue: ") == 'y':
    populate()
else:
    print('Aborting')
