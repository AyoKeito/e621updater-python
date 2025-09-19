# e621updater-python

[e621updater](https://github.com/AyoKeito/e621updater) rewritten in Python.  
This script provides automated tagging of local images using the e621 database. It works reliably on Windows systems.
Contributions and improvements are welcome.  

You will need exiftool.exe (https://www.sno.phy.queensu.ca/~phil/exiftool/) in the working folder. It will be downloaded automatically if it doesn't exist. 

Tested and working with Python 3.10, 3.11, and 3.12, along with the dependencies listed in requirements.txt on Windows 10/11.

## Quick Start

1. Download and extract the project
2. Run `start.bat` (Windows) or install dependencies with `pip install -r requirements.txt`
3. Wait for database download (~1.6GB) and processing (~10-15 minutes)
4. Select your image folder when prompted
5. Images will be automatically tagged with e621 metadata

## Prerequisites

- **Python**: 3.10, 3.11, or 3.12
- **Operating System**: Windows 10/11 (tested)
- **RAM**: ~7.5GB free memory for database processing
- **Storage**: ~5GB free space for database files
- **Internet**: Stable connection for initial 1.6GB download

## Installation

Download the script using git:
```bash
git clone https://github.com/AyoKeito/e621updater-python
```

Or download a zip archive from the [Releases](https://github.com/AyoKeito/e621updater-python/releases) page.

## Windows Batch Script (start.bat)
If needed, it creates a venv in the script's folder and installs the required dependencies.
After that, it runs both scripts using this venv. database.py will start first with the `-m` flag, followed by tagger.py with the `-f` flag.
If you need to add or change any flags, you can edit the batch file with Notepad.

You can also run scripts manually, and/or without venv.

## Image Tagging (tagger.py)
![tagger.py](/img/PowerShell_2023-02-11_21_27_18.jpg)
```
usage: tagger.py [-h] [-f] [-t] [-p FOLDER_PATH] [-n]
```
tagger.py SHOULD be run with `-f, --in-file` or `-t, --in-txt` command line arguments:
| Flag        | Description |
|-------------|-------------|
| `-f`, `--in-file`  | Write tags to image EXIF |
| `-t`, `--in-txt`    | Write tags to sidecar txt files (useful for ML databases) |

Optionally, you can use the following command-line flags:

| Flag        | Description |
|-------------|-------------|
| `-p FOLDER_PATH`, `--folder-path FOLDER_PATH`  | Path to the folder containing the images, for example: F:\myfiles\test\. If not set, will be selected via GUI. |
| `-n`, `--no-rename`    | Do not rename the images if they are found by MD5 and not by name (you WON'T be able to tag them again) |

> [!IMPORTANT] 
> tagger.py **requires** parquet database of e621 posts and an additional tag database to separate artists from other tags.

## Database Download (database.py)
![database.py](/img/PowerShell_2023-02-11_21_33_46.jpg)
```
usage: database.py [-h] [-p PROXY] [-m]
```
Optionally, you can use these flags:
| Flag        | Description |
|-------------|-------------|
| `-p PROXY`, `--proxy PROXY`  | The proxy to use for all network calls. Usage examples: http://proxy.server:8888 or http://user:password@proxy.server:8888. Alternatively, create a proxy.txt file with the proxy URL. |
| `-m`, `--multithreaded`  | Use Modin RAY engine for multithreaded operations on database. |

> [!CAUTION]  
> database.py downloads around 1.6GB of data from https://e621.net/db_export/ each time it's run. You will be asked if you want to update the local database if it was downloaded before. If local database doesn't exist, it will be downloaded unconditionally.

~7.5GB of free RAM is required to run it.  
Around 4GB of files will be written to disk as a result: trimmed databases `posts.parquet` and `artists.parquet` and a temporary `latest_posts.csv` file.  
You don't need to update them unless you want to tag files added to e621 since the last time you've updated the database.  
Tagger WILL NOT succeed without the correctly prepared databases in its working folder.  
It will also fail to find any files uploaded to e621 after you've last updated the database via database.py.

If you have any problems running Modin/Ray with `-m` flag, simply remove it. If you want to avoid using temporary files for any reason, you can remove this flag and avoid 3GB of `latest_posts.csv` written to disk.

## Examples

### Basic Usage
```bash
# Download/update database (run first)
python database.py

# Tag images with EXIF metadata (recommended)
python tagger.py -f

# Tag images with sidecar txt files
python tagger.py -t
```

### Advanced Usage
```bash
# Use proxy for database download
python database.py -p http://proxy.server:8888

# Use multithreading (requires 7.5GB RAM)
python database.py -m

# Tag specific folder without renaming files
python tagger.py -f -p "C:\My Images" -n

# Create txt files for machine learning datasets
python tagger.py -t -p "C:\ML Dataset"
```

## Troubleshooting

### Common Issues

**"No database files found"**
- Run `python database.py` first to download the e621 database

**"Out of memory" during database processing**
- Close other applications to free up RAM
- Remove `-m` flag to use less memory (slower processing)

**"No images found" or "No tags applied"**
- Ensure images have MD5 hashes that match e621 posts
- Images must be uploaded to e621 before your last database update

**Proxy connection issues**
- Verify proxy URL format: `http://proxy.server:port`
- Try creating `proxy.txt` file with proxy URL instead of using `-p` flag

**ExifTool errors**
- Ensure `exiftool.exe` is in the working directory (auto-downloaded)
- Try running as administrator if file permission errors occur
