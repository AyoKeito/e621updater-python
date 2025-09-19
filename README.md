# e621updater-python

[e621updater](https://github.com/AyoKeito/e621updater) rewritten in Python.  
This script provides automated tagging of local images using the e621 database. It works reliably on Windows systems.
Contributions and improvements are welcome.  

You will need exiftool.exe (https://www.sno.phy.queensu.ca/~phil/exiftool/) in the working folder. It will be downloaded automatically if it doesn't exist. 

Tested and working with Python 3.10, 3.11, and 3.12, along with the dependencies listed in requirements.txt on Windows 10/11.  

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
> database.py downloads around 1.1GB of data from https://e621.net/db_export/ each time it's run. You will be asked if you want to update the local database if it was downloaded before. If local database doesn't exist, it will be downloaded unconditionally.

~7.5GB of free RAM is required to run it.  
Around 4GB of files will be written to disk as a result: trimmed databases `posts.parquet` and `artists.parquet` and a temporary `latest_posts.csv` file.  
You don't need to update them unless you want to tag files added to e621 since the last time you've updated the database.  
Tagger WILL NOT succeed without the correctly prepared databases in its working folder.  
It will also fail to find any files uploaded to e621 after you've last updated the database via database.py.

If you have any problems running Modin/Ray with `-m` flag, simply remove it. If you want to avoid using temporary files for any reason, you can remove this flag and avoid 3GB of `latest_posts.csv` written to disk.
