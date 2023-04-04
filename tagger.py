"""
e621 tagger

Author: AyoKeito
Version: 1.0.1
GitHub: https://github.com/AyoKeito/e621updater-python

Let's tag your yiff!
"""

import os
import hashlib
import pandas as pd
import argparse
from tkinter import Tk
from tkinter.filedialog import askdirectory
import exiftool
import shutil

def select_folder():
    Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
    folder_selected = askdirectory() # show an "Open" dialog box and return the path to the selected folder
    return folder_selected

def build_list_of_images(folder_path):
    return [filename for filename in os.listdir(folder_path)
            if filename.lower().endswith((".png", ".jpg", ".jpeg"))]

def calculate_md5(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def search_in_posts(file_name, file_md5, posts_df):
    mask = posts_df["md5"].isin([file_name, file_md5])
    matching_rows = posts_df[mask]
    if len(matching_rows) > 0:
        return matching_rows.iloc[0]["tag_string"]
    else:
        return None

def write_to_exif(file_path, tag_string):
    if tag_string is not None:
        artists_df = pd.read_parquet("artists.parquet")
        artists_list = set(artists_df['name'])
        trash_tags = {"conditional_dnp", "avoid_posting", "unknown_artist", "absurd_res", "hi_res", "digital_media_(artwork)", "traditional_media_(artwork)"}
        subject_tags = ", ".join(tag for tag in tag_string.split(", ") if tag not in trash_tags and tag not in artists_list)
        creator_tags = ", ".join(tag for tag in tag_string.split(", ") if tag in artists_list)
        with exiftool.ExifTool() as et:
            et.execute(f"-xmp-dc:subject={subject_tags}", "-overwrite_original_in_place", file_path)
            et.execute(f"-xmp-dc:creator={creator_tags}", "-overwrite_original_in_place", file_path)

def write_to_txt(file_path, tag_string):
    txt_file_path = os.path.splitext(file_path)[0] + ".txt"
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(tag_string)

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--in-file", help="Write the tags found in database to image EXIF", action='store_true')
parser.add_argument("-t", "--in-txt", help="Write the tags to sidecar txt files (useful for ML databases)", action='store_true')
parser.add_argument("-p", "--folder-path", help="Path to the folder containing the images, for example: F:\\myfiles\\test\\", type=str)
parser.add_argument("-n", "--no-rename", help="Do not rename the images if they are found by MD5 and not by name (you \033[4mWON'T\033[0m be able to tag them again)", action='store_true')
args = parser.parse_args()

if not args.in_file and not args.in_txt:
    parser.error("At least one of the arguments --in-file (-f) or --in-txt (-t) must be specified")
if args.folder_path:
    folder_path = args.folder_path
else:
    folder_path = select_folder()

list_of_images = build_list_of_images(folder_path)
posts_df = pd.read_parquet("posts.parquet")
processed_count = 0
not_found = []
renamed_files = []
total_files = len(list_of_images)

print("{:<6} {:<36} {:<14} {:<30}".format("%", "Name", "Found/Missing", "Tags"))
for image_file in list_of_images:
    file_path = os.path.join(folder_path, image_file)
    file_name_without_extension, file_extension = os.path.splitext(image_file)
    tag_string, found_by = "MISSING", "MISSING"
    if (tag_string := search_in_posts(file_name_without_extension, None, posts_df)) is not None:
        tag_string, found_by = tag_string.replace(" ", ", "), "Found (NAME)"
    else:
        if (tag_string := search_in_posts(None, calculate_md5(file_path), posts_df)) is not None:
            tag_string, found_by = tag_string.replace(" ", ", "), "Found (MD5)"
    if found_by == "MISSING":
        not_found.append(file_path)
    elif found_by == "Found (MD5)":
        new_file_name = f"{calculate_md5(file_path)}{file_extension}"
        if not args.no_rename:
            os.rename(file_path, os.path.join(folder_path, new_file_name))
            renamed_files.append((image_file, new_file_name))
    if args.in_file:
        write_to_exif(file_path, tag_string)
    if args.in_txt:
        write_to_txt(file_path, tag_string)
    if tag_string:
        tag_string = tag_string[:30]
    else:
        tag_string = ""
    print(f"\033[{31 if found_by == 'MISSING' else 33 if found_by == 'Found (MD5)' else 32}m{f'{(processed_count/total_files)*100:.2f}%':<6} {image_file:<36} {found_by:<14} {tag_string:<30}\033[0m")
    processed_count += 1

if not_found:
    not_found_directory = os.path.join(folder_path, "NotFound")
    os.makedirs(not_found_directory, exist_ok=True)
    for file_path in not_found:
        destination_path = os.path.join(not_found_directory, os.path.basename(file_path))
        shutil.move(file_path, not_found_directory)
    print("Processed image", processed_count, "of", len(list_of_images), "\n", len(not_found), "files are not found")
else:
    print("Processed image", processed_count, "of", len(list_of_images), "\n", "All files are found")

print("Finished processing all images.")

if renamed_files:
    with open(os.path.join(folder_path, "_renamed_files.txt"), "w") as file:
        for original_name, new_name in renamed_files:
            file.write(f"{original_name} renamed to {new_name}\n")
    print("Renamed files list saved to renamed_files.txt")
