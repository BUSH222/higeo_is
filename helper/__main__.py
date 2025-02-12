from .db.populate import populate

a = input("Populating the table with dummy data, y to continue: ")
if a == 'y':
    populate()
else:
    print('Aborting')
