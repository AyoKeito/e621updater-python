"""
e621 tagger - database updater

Author: AyoKeito
Version: 1.3
GitHub: https://github.com/AyoKeito/e621updater-python
"""

import re
import asyncio
import aiohttp
import gzip
import pandas as pds
import argparse
import io
import os
import zipfile
import traceback
import time
import datetime as dt
import sys
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn, DownloadColumn, TransferSpeedColumn
from rich.console import Console

parser = argparse.ArgumentParser(description="Download and process CSV files. Download gz archives, extract & filter irrelevant data, and save as compressed parquet files.")
parser.add_argument("--proxy", help="The proxy to use for all network calls (optional). Usage examples: http://proxy.server:8888 or http://user:password@proxy.server:8888")
parser.add_argument("-m", "--multithreaded", action="store_true", help="Use Modin RAY engine for multithreaded operations on database.")
args = parser.parse_args()

# Check for proxy.txt file if no proxy argument provided
if not args.proxy and os.path.exists("proxy.txt"):
    try:
        with open("proxy.txt", "r", encoding="utf-8") as f:
            proxy_from_file = f.read().strip()
            if proxy_from_file:
                args.proxy = proxy_from_file
                print(f"Using proxy from proxy.txt: {args.proxy}")
    except Exception as e:
        print(f"Warning: Could not read proxy.txt: {e}")

if args.multithreaded:
    import ray
    import modin.pandas as pd
    import modin

# Try to use Polars for better performance, fall back to pandas if not available
try:
    import polars as pl
    use_polars = True
    print("Using Polars for optimized performance")
except ImportError:
    use_polars = False
    print("Polars not available, using pandas")  

def check_database_update(web_date):
    if os.path.exists("artists.parquet"):
        modification_time = os.path.getmtime("artists.parquet")
        # Replaced dt.datetime.utcfromtimestamp(modification_time) with dt.datetime.fromtimestamp(modification_time, tz=dt.timezone.utc) to create an offset-aware datetime in UTC.
        modification_datetime = dt.datetime.fromtimestamp(modification_time, tz=dt.timezone.utc)
        # Added replace(tzinfo=dt.timezone.utc) to the web_datetime to ensure it is also offset-aware in UTC.
        web_datetime = dt.datetime.strptime(web_date, '%d-%b-%Y %H:%M').replace(tzinfo=dt.timezone.utc)

        print(f"Local posts database date: \033[96m{modification_datetime.strftime('%d-%b-%Y %H:%M')}\033[0m")

        time_difference = modification_datetime - web_datetime
        if modification_datetime >= web_datetime:
            print(f"Database is up-to-date.")
            return True
        else:
            print(f"Database is outdated by \033[1m{abs(time_difference.days)}\033[0m days.")
            return False

    return False

async def download_file(session, url, destination=None, progress_bar=None, task_id=None, description="Downloading"):
    async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
        if resp.status == 200:
            total_size = int(resp.headers.get('content-length', 0))
            content = bytearray()

            # Use provided progress bar or create a simple one
            if progress_bar and task_id is not None:
                # Update the existing task with total size and description
                progress_bar.update(task_id, total=total_size, description=description)

                async for chunk in resp.content.iter_any():
                    content.extend(chunk)
                    chunk_size = len(chunk)
                    progress_bar.update(task_id, advance=chunk_size)
            else:
                # Fallback: create simple progress bar for standalone downloads
                progress = Progress(
                    TextColumn("[bold blue]Downloading", justify="right"),
                    BarColumn(bar_width=40),
                    "[progress.percentage]{task.percentage:>3.1f}%",
                    "•",
                    DownloadColumn(),
                    "•",
                    TransferSpeedColumn(),
                    console=Console(),
                    transient=False
                )

                with progress:
                    if total_size > 0:
                        task = progress.add_task("download", total=total_size)
                    else:
                        task = progress.add_task("download", total=None)

                    async for chunk in resp.content.iter_any():
                        content.extend(chunk)
                        chunk_size = len(chunk)
                        progress.update(task, advance=chunk_size)

            if destination:
                with open(destination, 'wb') as f:
                    f.write(content)

            return content
            
async def download_exiftool(session):
    exiftool_url = "https://sourceforge.net/projects/exiftool/files/latest/download"
    if not os.path.exists("exiftool.exe"):
        print(f"Downloading ExifTool from {exiftool_url}")
        exiftool_content = await download_file(session, exiftool_url, destination="exiftool.zip")

        if exiftool_content:
            print("Extracting ExifTool executable")
            with zipfile.ZipFile(io.BytesIO(exiftool_content), 'r') as zip_ref:
                # Find exiftool(-k).exe in the versioned folder
                exiftool_path = None
                version_dir = None
                for name in zip_ref.namelist():
                    if name.endswith('exiftool(-k).exe'):
                        exiftool_path = name
                        version_dir = name.split('/')[0]
                        break

                if exiftool_path and version_dir:
                    # Extract the entire contents to preserve dependencies
                    zip_ref.extractall()
                    # Move exiftool(-k).exe to working directory and rename
                    os.rename(exiftool_path, "exiftool.exe")
                    # Move exiftool_files directory to working directory (needed for dependencies)
                    import shutil
                    exiftool_files_path = f"{version_dir}/exiftool_files"
                    if os.path.exists(exiftool_files_path):
                        if os.path.exists("exiftool_files"):
                            shutil.rmtree("exiftool_files")
                        shutil.move(exiftool_files_path, "exiftool_files")
                    # Clean up the extracted version directory
                    if os.path.exists(version_dir):
                        shutil.rmtree(version_dir)

            os.remove('exiftool.zip') if os.path.exists('exiftool.zip') else None
    else:
        print("ExifTool already exists. Skipping download.")

async def main(url, proxy, use_multithreaded=False):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
                if resp.status == 200:
                    await download_exiftool(session)  # Pass the session to download_exiftool function
                    print(f"\033[1mStep 1:\033[0m Got response from \033[96m{url}\033[0m")
                    content = await resp.text()
                    file_links = re.findall(r'<a href="(.*?)">', content)
                    # After finding the latest_posts link
                    posts_files = [x for x in file_links if x.startswith("posts")]
                    if not posts_files:
                        print("Error: No posts files found on the server.")
                        return
                    latest_posts_link = sorted(posts_files, reverse=True)[0]

                    # Escape special characters in the latest_posts_link
                    escaped_latest_posts_link = re.escape(latest_posts_link)

                    # Construct the regex pattern using f-string
                    regex_pattern = rf'<a href="{escaped_latest_posts_link}">(.*?)</a>\s+(\d{{2}}-[a-zA-Z]{{3}}-\d{{4}} \d{{2}}:\d{{2}})\s+(\d+)'

                    # Extracting the filename and filesize using a regular expression
                    file_info_match = re.search(regex_pattern, content)

                    if file_info_match:
                        filename = file_info_match.group(1)
                        date = file_info_match.group(2)
                        filesize = int(file_info_match.group(3))
                        filesize_mb = filesize / (1024 ** 2)  # Convert bytes to megabytes

                        print(f"Latest posts file: \033[96m{filename}\033[0m")
                        print(f"Date: \033[96m{date}\033[0m")
                        print(f"Filesize: \033[96m{filesize_mb:.2f} MB\033[0m")  # Print filesize in megabytes with two decimal places
                        
                    # Check if the database is up-to-date
                    database_updated = check_database_update(date)
                    if not os.path.exists("artists.parquet"):
                        # If the file doesn't exist, update unconditionally
                        print("Downloading the database since the file doesn't exist.")
                        update_choice = 'y'  # Set update_choice to 'y' to proceed with the update unconditionally
                    elif not database_updated:
                        # If the file exists but is outdated, prompt the user
                        update_choice = input("\033[1mThe local database is outdated. Do you want to update? (Y/N):\033[0m ").lower().strip()
                        if update_choice not in ['y', 'yes', 'n', 'no']:
                            print("Invalid input, defaulting to 'no'")
                            update_choice = 'n'
                    else:
                        # If the file exists and is up-to-date, skip the update
                        print("Recent database, skipping downloads.")
                        return

                    # Check if user wants to proceed with the update
                    if update_choice in ['n', 'no']:
                        print("Database update skipped by user choice.")
                        return

                    # Continue with the update process
                    try:
                        # Create unified progress bar for all operations
                        main_progress = Progress(
                            TextColumn("[bold cyan]{task.description}", justify="right"),
                            BarColumn(bar_width=40),
                            "[progress.percentage]{task.percentage:>3.1f}%",
                            "•",
                            DownloadColumn(),
                            "•",
                            TransferSpeedColumn(),
                            "•",
                            TimeRemainingColumn(),
                            console=Console(),
                            transient=False
                        )

                        with main_progress:
                            print(f"\033[1mStep 2:\033[0m Downloading \033[96m{latest_posts_link}\033[0m")
                            start_time = time.time()

                            # Create download task
                            download_task = main_progress.add_task("Downloading posts database...", total=None)
                            posts_content = gzip.decompress(await download_file(session, url + latest_posts_link,
                                                                               progress_bar=main_progress, task_id=download_task))

                            end_time = time.time()
                            time_taken = end_time - start_time
                            print(f"Downloaded {latest_posts_link} in {time_taken:.2f} seconds.")

                            if use_multithreaded:
                                with open('latest_posts.csv', 'wb') as f:
                                    f.write(posts_content)
                                del posts_content
                                print(f"Processing in \033[92mmultithreaded\033[0m mode, \033[92m{modin.config.NPartitions.get()}\033[0m threads detected, initializing Modin RAY engine...")
                                ray.init()
                            else:
                                print(f"Processing in \033[93msinglethreaded\033[0m mode...")

                            print(f"\033[1mStep 3:\033[0m Reading extracted posts CSV as a DataFrame")
                            if use_polars and not use_multithreaded:
                                # Use Polars for optimal performance (6x faster)
                                posts_df = pl.read_csv(io.BytesIO(posts_content), columns=["id", "md5", "tag_string"])
                                del posts_content
                            elif use_multithreaded:
                                posts_df = pd.read_csv('latest_posts.csv', usecols=["id", "md5", "tag_string"])
                            else:
                                posts_df = pds.read_csv(io.BytesIO(posts_content), usecols=["id", "md5", "tag_string"])
                                del posts_content

                            print(f"\033[1mStep 4:\033[0m Saving DataFrame to posts.parquet")
                            if use_multithreaded:
                                os.remove('latest_posts.csv')  # Delete the temporary file
                                posts_df.to_parquet("posts.parquet", engine='pyarrow', compression='zstd')
                                ray.shutdown()
                            elif use_polars:
                                posts_df.write_parquet("posts.parquet", compression="zstd")
                            else:
                                posts_df.to_parquet("posts.parquet", engine='pyarrow', compression='zstd')

                        del posts_df
                        print(f"\033[32mStep 5:\033[0m posts.parquet done!\033[0m")
                    except Exception as e:
                        print("An error occurred while downloading or processing the latest posts:", e)
                        traceback.print_exc()
                        return

                    tags_files = [x for x in file_links if x.startswith("tags")]
                    if not tags_files:
                        print("Error: No tags files found on the server.")
                        return
                    latest_tags = sorted(tags_files, reverse=True)[0]
                    try:
                        # Create unified progress bar for tags operations
                        tags_progress = Progress(
                            TextColumn("[bold cyan]{task.description}", justify="right"),
                            BarColumn(bar_width=40),
                            "[progress.percentage]{task.percentage:>3.1f}%",
                            "•",
                            DownloadColumn(),
                            "•",
                            TransferSpeedColumn(),
                            "•",
                            TimeRemainingColumn(),
                            console=Console(),
                            transient=False
                        )

                        with tags_progress:
                            print(f"\033[1mStep 6:\033[0m Downloading latest tags file {latest_tags}")

                            # Create download task for tags
                            tags_download_task = tags_progress.add_task("Downloading tags database...", total=None)
                            tags_content = gzip.decompress(await download_file(session, url + latest_tags,
                                                                              progress_bar=tags_progress, task_id=tags_download_task)).decode()

                            print(f"\033[1mStep 7:\033[0m Reading {latest_tags} as a DataFrame")
                            if use_polars:
                                # Use Polars for faster processing
                                df = pl.read_csv(io.BytesIO(bytes(tags_content, "utf-8")),
                                               schema_overrides={"id": pl.Int64, "name": pl.Utf8, "category": pl.Int64, "post_count": pl.Int64})

                                print(f"\033[1mStep 8:\033[0m Filtering DataFrame to only include rows where category is equal to 1 (artists)")
                                print(f"\033[1mStep 9:\033[0m Keeping only the 'name' column from the DataFrame")
                                # Filter and select in one operation with Polars
                                df = df.filter(pl.col("category") == 1).select("name")
                            else:
                                df = pds.read_csv(io.BytesIO(bytes(tags_content, "utf-8")), header=0, dtype={"id": int, "name": str, "category": int, "post_count": int})

                                print(f"\033[1mStep 8:\033[0m Filtering DataFrame to only include rows where category is equal to 1 (artists)")
                                df = df[df["category"] == 1]

                                print(f"\033[1mStep 9:\033[0m Keeping only the 'name' column from the DataFrame")
                                df = df[["name"]]

                            print(f"\033[1mStep 10:\033[0m Saving DataFrame to artists.parquet")
                            if os.path.exists('artists.parquet'):
                                os.remove('artists.parquet')

                            if use_polars:
                                df.write_parquet("artists.parquet", compression="zstd")
                            else:
                                df.to_parquet("artists.parquet", engine='pyarrow', compression='zstd')

                        print(f"\033[32mStep 11:\033[0m artists.parquet done!\033[0m")
                        del df
                    except Exception as e:
                        print("An error occurred while downloading or processing the latest tags:", e)
                        traceback.print_exc()
                        return
    except Exception as e:
        print("A network error occurred:", e)
        print("Try to restart the script with the --proxy argument.")
        traceback.print_exc()

# Usage:
try:
    asyncio.run(main("https://e621.net/db_export/", proxy=args.proxy, use_multithreaded=args.multithreaded))
except Exception as e:
    print("An unexpected error occurred:", e)
    traceback.print_exc()

