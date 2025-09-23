"""
e621 tagger

Author: AyoKeito
Version: 1.3
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
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.console import Console

# Optimized file extension checking
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}

def crop_filename(filename, max_length=36):
    """Crop filename to specified length, adding ellipsis if needed"""
    if len(filename) <= max_length:
        return filename
    return filename[:max_length-3] + "..."

def select_folder():
    Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
    folder_selected = askdirectory() # show an "Open" dialog box and return the path to the selected folder
    return folder_selected

def build_list_of_images(folder_path):
    list_of_images = []
    for filename in os.listdir(folder_path):
        if any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            list_of_images.append(filename)
    return list_of_images

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):  # Larger chunk size for better performance
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def calculate_md5_cached(file_path, cache):
    """Calculate MD5 with caching to avoid redundant calculations"""
    if file_path in cache:
        return cache[file_path]

    md5_hash = calculate_md5(file_path)
    cache[file_path] = md5_hash
    return md5_hash

def search_in_posts(file_name, file_md5, md5_to_tags_dict):
    # O(1) dictionary lookups instead of O(n) DataFrame searches
    if file_name and file_name in md5_to_tags_dict:
        return md5_to_tags_dict[file_name]
    elif file_md5 and file_md5 in md5_to_tags_dict:
        return md5_to_tags_dict[file_md5]
    else:
        return None

def write_to_exif(file_path, tag_string, artists_set):
    subject_tags = []
    creator_tags = []
    tags = tag_string.split("; ")
    trash_tags = {"conditional_dnp", "avoid_posting", "unknown_artist", "absurd_res", "hi_res", "digital_media_(artwork)", "traditional_media_(artwork)"}  # Using set for O(1) lookups

    for tag in tags:
        # Filter out problematic characters and ensure ASCII compatibility
        clean_tag = tag.encode('ascii', 'ignore').decode('ascii')
        if clean_tag:  # Only add if tag still has content after cleaning
            # Check original tag for artist membership since artists_set contains original tags
            if tag in artists_set:  # O(1) set lookup using original tag
                creator_tags.append(clean_tag)
            elif clean_tag not in trash_tags:
                subject_tags.append(clean_tag)

    subject_tags_str = "; ".join(subject_tags)
    creator_tags_str = "; ".join(creator_tags)

    exiftool_path = os.path.abspath("exiftool.exe")
    try:
        with exiftool.ExifTool(exiftool_path, encoding='utf-8') as et:
            if subject_tags_str:
                et.execute(f"-xmp-dc:subject={subject_tags_str}", "-overwrite_original_in_place", file_path)
            if creator_tags_str:
                et.execute(f"-xmp-dc:creator={creator_tags_str}", "-overwrite_original_in_place", file_path)
    except UnicodeEncodeError as e:
        print(f"Warning: Unicode encoding error for {file_path}: {e}")
        # Fallback: try with even more restrictive filtering
        try:
            # Remove any non-printable ASCII characters
            subject_clean = ''.join(c for c in subject_tags_str if ord(c) < 128 and c.isprintable())
            creator_clean = ''.join(c for c in creator_tags_str if ord(c) < 128 and c.isprintable())

            with exiftool.ExifTool(exiftool_path) as et:
                if subject_clean:
                    et.execute(f"-xmp-dc:subject={subject_clean}", "-overwrite_original_in_place", file_path)
                if creator_clean:
                    et.execute(f"-xmp-dc:creator={creator_clean}", "-overwrite_original_in_place", file_path)
        except Exception as fallback_error:
            print(f"Error: Could not write EXIF data to {file_path}: {fallback_error}")

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

# Initialize caches and optimized data structures
md5_cache = {}  # Cache for calculated MD5s to avoid redundant calculations

start_time = time.time()
print(f"Loading posts.parquet database...")

posts_df = pd.read_parquet("posts.parquet")

# Create O(1) lookup dictionary for MD5 to tags mapping
print(f"Creating MD5 index for faster lookups...")
md5_to_tags = dict(zip(posts_df['md5'], posts_df['tag_string']))

print(f"Loading artists.parquet database...")
artists_df = pd.read_parquet("artists.parquet")
artists_set = set(artists_df['name'].tolist())  # Convert to set for O(1) lookups

print(f"Database loading completed. Loaded {len(md5_to_tags)} posts and {len(artists_set)} artists.")

processed_count = 0
not_found = []
renamed_files = []

total_files = len(list_of_images)

# Initialize Rich console and progress display
console = Console()

# Create clean progress bar
progress = Progress(
    TextColumn("[bold blue]Processing files", justify="right"),
    BarColumn(bar_width=40),
    "[progress.percentage]{task.percentage:>3.1f}%",
    "•",
    TextColumn("[bold green]{task.completed}/{task.total}"),
    "•",
    TimeElapsedColumn(),
    "•",
    TimeRemainingColumn(),
    console=console,
    transient=False
)

print("{:<6} {:<36} {:<14} {:<30}".format("%", "Name", "Found/Missing", "Tags"))

with progress:
    task = progress.add_task("processing", total=total_files)

    for image_file in list_of_images:
        file_path = os.path.join(folder_path, image_file)
        file_name_without_extension, file_extension = os.path.splitext(image_file)

        # Try filename lookup first using optimized dictionary
        tag_string = search_in_posts(file_name_without_extension, None, md5_to_tags)
        file_md5 = None

        if tag_string is None:
            # Calculate MD5 with caching and try MD5 lookup
            file_md5 = calculate_md5_cached(file_path, md5_cache)
            tag_string = search_in_posts(None, file_md5, md5_to_tags)
            if tag_string is not None:
                found_by = "Found (MD5)"
                tag_string = tag_string.replace(" ", "; ")
            else:
                tag_string = "MISSING"
                found_by = "MISSING"
        else:
            found_by = "Found (NAME)"
            tag_string = tag_string.replace(" ", "; ")

        # Write tags using optimized functions
        if args.in_file and tag_string != "MISSING":
            write_to_exif(file_path, tag_string, artists_set)
        if args.in_txt:
            write_to_txt(file_path, tag_string)

        # Handle results and display progress
        if found_by == "MISSING":
            print("\033[31m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", crop_filename(image_file), found_by, tag_string[:30]))
            not_found.append(file_path)
        elif found_by == "Found (MD5)":
            print("\033[33m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", crop_filename(image_file), found_by, tag_string[:30]))
            if not args.no_rename:
                # Use cached MD5 for renaming (we already calculated it)
                new_file_name = f"{file_md5}{file_extension}"
                new_file_path = os.path.join(folder_path, new_file_name)

                # Handle file collision - if target file already exists
                if os.path.exists(new_file_path):
                    # Check if it's the same file (already correctly named)
                    if os.path.samefile(file_path, new_file_path):
                        # File is already correctly named, nothing to do
                        pass
                    else:
                        # Target filename exists but is a different file
                        # Add a counter to make the filename unique
                        base_name = file_md5
                        counter = 1
                        while os.path.exists(new_file_path):
                            new_file_name = f"{base_name}_{counter}{file_extension}"
                            new_file_path = os.path.join(folder_path, new_file_name)
                            counter += 1

                        try:
                            os.rename(file_path, new_file_path)
                            renamed_files.append((image_file, new_file_name))
                        except OSError as e:
                            print(f"Warning: Could not rename {image_file} to {new_file_name}: {e}")
                else:
                    # Target doesn't exist, safe to rename
                    try:
                        os.rename(file_path, new_file_path)
                        renamed_files.append((image_file, new_file_name))
                    except OSError as e:
                        print(f"Warning: Could not rename {image_file} to {new_file_name}: {e}")
        else:  # Found (NAME)
            print("\033[32m{:<6} {:<36} {:<14} {:<30}\033[0m".format(f"{(processed_count/total_files)*100:.2f}%", crop_filename(image_file), found_by, tag_string[:30]))

        processed_count += 1
        progress.update(task, advance=1)

if len(not_found) == 0:
    print("Processed", processed_count, "images\nAll files are found")
else:
    print("Processed", processed_count, "images\n", len(not_found), "files are not found")

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
