"""
e621 tagger

Author: AyoKeito
Version: 1.2
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
import time

def select_folder():
    Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
    folder_selected = askdirectory() # show an "Open" dialog box and return the path to the selected folder
    return folder_selected

def build_list_of_images(folder_path):
    list_of_images = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".png") or filename.endswith(".jpg") or filename.endswith(".jpeg"):
            list_of_images.append(filename)
    return list_of_images

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def search_in_posts(file_name, file_md5, posts_df):
    if file_name in list(posts_df["md5"]):
        index = posts_df[posts_df["md5"] == file_name].index.tolist()[0]
        return posts_df.at[index, "tag_string"]
    elif file_md5 in list(posts_df["md5"]):
        index = posts_df[posts_df["md5"] == file_md5].index.tolist()[0]
        return posts_df.at[index, "tag_string"]
    else:
        #print("File:", file_name, " not found in the posts data")
        return None

def write_to_exif(file_path, tag_string, artists_list):
    subject_tags = []
    creator_tags = []
    tags = tag_string.split(", ")
    trash_tags = ["conditional_dnp", "avoid_posting", "unknown_artist", "absurd_res", "hi_res", "digital_media_(artwork)", "traditional_media_(artwork)"]
    for tag in tags:
        if tag in artists_list:
            creator_tags.append(tag)
        elif tag not in trash_tags:
            subject_tags.append(tag)
    subject_tags = ", ".join(subject_tags)
    creator_tags = ", ".join(creator_tags)
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

# Validate folder path
if not folder_path or folder_path.strip() == "":
    print("Error: No folder selected. Exiting.")
    exit(1)

if not os.path.exists(folder_path):
    print(f"Error: The specified folder does not exist: {folder_path}")
    exit(1)

if not os.path.isdir(folder_path):
    print(f"Error: The specified path is not a folder: {folder_path}")
    exit(1)

list_of_images = build_list_of_images(folder_path)

start_time = time.time()
print(f"Loading posts.parquet database...")

posts_df = pd.read_parquet("posts.parquet")

print(f"Loading artists.parquet database...")
artists_df = pd.read_parquet("artists.parquet")
artists_list = artists_df['name'].tolist()

processed_count = 0
not_found = []
renamed_files = []

total_files = len(list_of_images)

print("{:<6} {:<36} {:<14} {:<30}".format("%", "Name", "Found/Missing", "Tags"))
for image_file in list_of_images:
    file_path = os.path.join(folder_path, image_file)
    file_name_without_extension, file_extension = os.path.splitext(image_file)
    tag_string = search_in_posts(file_name_without_extension, None, posts_df)
    found_by = "Found (NAME)"
    if tag_string is None:
        file_md5 = calculate_md5(file_path)
        tag_string = search_in_posts(None, file_md5, posts_df)
        if tag_string is not None:
            found_by = "Found (MD5)"
            tag_string = tag_string.replace(" ", ", ")
        else:
            tag_string = "MISSING"
            found_by = "MISSING"
    else:
        found_by = "Found (NAME)"
        tag_string = tag_string.replace(" ", ", ")
    if args.in_file and tag_string != "MISSING":
        write_to_exif(file_path, tag_string, artists_list)
    if args.in_txt:
        write_to_txt(file_path, tag_string)
    if found_by == "MISSING":
        #print("\033[31m{:<36} {:<12} {:<30}\033[0m".format(image_file, found_by, tag_string[:30]))
        print("\033[31m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", image_file, found_by, tag_string[:30]))
        not_found.append(file_path)
    if found_by == "Found (MD5)":
        if args.no_rename:
            #print("\033[33m{:<36} {:<12} {:<30}\033[0m".format(image_file, found_by, tag_string[:30]))
            print("\033[33m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", image_file, found_by, tag_string[:30]))
        else:
            #print("\033[33m{:<36} {:<12} {:<30}\033[0m".format(image_file, found_by, tag_string[:30]))
            print("\033[33m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", image_file, found_by, tag_string[:30]))
            # Ensure we have the MD5 hash for renaming
            if 'file_md5' not in locals():
                file_md5 = calculate_md5(file_path)
            new_file_name = f"{file_md5}{file_extension}"
            os.rename(file_path, os.path.join(folder_path, new_file_name))
            renamed_files.append((image_file, new_file_name))
    if found_by == "Found (NAME)":
        #print("\033[32m{:<36} {:<12} {:<30}\033[0m".format(image_file, found_by, tag_string[:30]))
        print("\033[32m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", image_file, found_by, tag_string[:30]))
    processed_count += 1

if len(not_found) == 0:
    print("Processed image", processed_count, "of", len(list_of_images), "\n", "All files are found")
else:
    print("Processed image", processed_count, "of", len(list_of_images), "\n", len(not_found), "files are not found")

if len(not_found) > 0:
    not_found_directory = os.path.join(folder_path, "NotFound")
    os.makedirs(not_found_directory, exist_ok=True)
    
    for file_path in not_found:
        destination_path = os.path.join(not_found_directory, os.path.basename(file_path))

        try:
            shutil.move(file_path, not_found_directory)
        except shutil.Error as e:
            # Handle the error here, for example, by printing a message
            print(f"Error moving file: {e}")
            # You can choose to overwrite the file if it already exists
            shutil.copy2(file_path, destination_path)
            os.remove(file_path)  # Remove original after successful copy
            print(f"Copied and removed original: {file_path} -> {destination_path}")

end_time = time.time()
time_taken = end_time - start_time
print(f"Processed {processed_count} files in {time_taken:.2f} seconds.")
print("Finished processing all images.")

if len(renamed_files) > 0:
    with open(os.path.join(folder_path, "_renamed_files.txt"), "w") as file:
        for original_name, new_name in renamed_files:
            file.write(f"{original_name} renamed to {new_name}\n")
    print("Renamed files list saved to renamed_files.txt")
