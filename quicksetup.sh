#!/bin/bash
cd "$(dirname "$0")"
python3 -m helper
python3 -m misc.convert

read -p "Do you want to migrate over files? (y/n): " migrate_files
if [[ "$migrate_files" == "y" || "$migrate_files" == "Y" ]]; then
    read -p "Enter the path to the original files: " input_folder
    python3 -m misc.convert_files "$input_folder"
fi
echo "Setup complete!"