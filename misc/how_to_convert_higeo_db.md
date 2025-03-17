# How to convert the old database into the new one
1. Download Datagrip (Jetbrains) \
This can also be done without datagrip, just with mysql commands
2. Connect an empty mysql database
3. Import your sql data dump (Database name -> Import/Export -> Restore with mysql)
4. Export the following tables as csv without headers: author, employ, org, person, pub, source
5. Compress the csv files into the archive data.zip and put it in the misc folder of this project, along with convert.py 
6. run `python3 misc/convert.py` from the project directory, ensure the postgres database is created (read readme)

