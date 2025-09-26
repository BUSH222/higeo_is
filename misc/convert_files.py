import os
import re
import shutil
import argparse
from datetime import datetime
from sqlalchemy.orm import Session
from helper.db.initialise_database import engine, Person, Document


def migrate_file(filename, prefix, old_files_dir, new_files_dir):
    match = re.match(rf'{prefix}-fil-(\d+)\.(jpg|jpeg|png|pdf|gif|JPG|tiff|bmp|tif)', filename)
    if not match:
        return None, None
    oldid = int(match.group(1))
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    new_filename = f"[{timestamp}]{filename}"
    src = os.path.join(old_files_dir, filename)
    dst = os.path.join(new_files_dir, new_filename)
    shutil.copy2(src, dst)
    return oldid, dst


def update_database(old_files_dir, new_files_dir):
    with Session(engine) as session:
        # Migrate photos for Person
        for fname in os.listdir(old_files_dir):
            if fname.startswith('photo-fil-'):
                oldid, new_path = migrate_file(fname, 'photo', old_files_dir, new_files_dir)
                if oldid and new_path:
                    person = session.query(Person).filter_by(_oldid=oldid).first()
                    if person:
                        person.photo = new_path
                        print(f"Updated Person {person.id} photo: {new_path}")
        # Migrate documents for Document
        for fname in os.listdir(old_files_dir):
            if fname.startswith('pub-fil-'):
                oldid, new_path = migrate_file(fname, 'pub', old_files_dir, new_files_dir)
                if oldid and new_path:
                    doc = session.query(Document).filter_by(_oldid=oldid).first()
                    if doc:
                        doc.file = new_path
                        print(f"Updated Document {doc.id} file: {new_path}")
        # Replace URLs in photo/file fields with new local path if file exists
        for person in session.query(Person).filter(Person.photo.like('http%')).all():
            match = re.search(r'photo-fil-(\d+)\.(jpg|jpeg|png|pdf|gif|JPG|tiff|bmp|tif)', person.photo)
            if match:
                oldid = int(match.group(1))
                ext = match.group(2)
                fname = f"photo-fil-{oldid}.{ext}"
                if os.path.exists(os.path.join(new_files_dir, fname)):
                    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                    new_filename = f"[{timestamp}]{fname}"
                    shutil.copy2(os.path.join(old_files_dir, fname), os.path.join(new_files_dir, new_filename))
                    person.photo = os.path.join(new_files_dir, new_filename)
                    print(f"Replaced URL for Person {person.id} photo: {person.photo}")
        for doc in session.query(Document).filter(Document.file.like('http%')).all():
            match = re.search(r'pub-fil-(\d+)\.(jpg|jpeg|png|pdf|gif|JPG|tiff|bmp|tif)', doc.file)
            if match:
                oldid = int(match.group(1))
                ext = match.group(2)
                fname = f"pub-fil-{oldid}.{ext}"
                if os.path.exists(os.path.join(new_files_dir, fname)):
                    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                    new_filename = f"[{timestamp}]{fname}"
                    shutil.copy2(os.path.join(old_files_dir, fname), os.path.join(new_files_dir, new_filename))
                    doc.file = os.path.join(new_files_dir, new_filename)
                    print(f"Replaced URL for Document {doc.id} file: {doc.file}")
        session.commit()


def main():
    parser = argparse.ArgumentParser(description="Migrate files and update database paths.")
    parser.add_argument('input_folder', help='Path to the folder containing old files')
    parser.add_argument('--output-folder', default='static/uploads', help='Path to the new uploads folder')
    args = parser.parse_args()

    os.makedirs(args.output_folder, exist_ok=True)
    update_database(args.input_folder, args.output_folder)
    print("Migration complete.")


if __name__ == "__main__":
    main()
