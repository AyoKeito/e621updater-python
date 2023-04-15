# e621updater-python

e621updater rewritten in python.  
This script is mostly written by OpenAI ChatGPT. It works, at least on my PC.  
There are a lot of things to improve in this code. Contributions are welcome.  

You will need exiftool.exe (https://www.sno.phy.queensu.ca/~phil/exiftool/) in the working folder.  

Tested and working as python scripts via Python 3.10 and a bunch of dependencies listed in requirements.txt on Windows 10\11.  
As this is the first Python thing i've done, i'm not sure requirements.txt is entirely correct. Some things may be missing. Feedback is welcome :)  
Compiled Windows build is also available in Releases. It should not require any dependencies on your side.

## Main script is tagger.py:
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
| `-p FOLDER_PATH`, `--folder-path FOLDER_PATH`  | Path to the folder containing the images, for example: F:\myfiles\test\ |
| `-n`, `--no-rename`    | Do not rename the images if they are found by MD5 and not by name (you WON'T be able to tag them again) |

> **Warning**
> tagger.py **requires** parquet database of e621 posts and an additional tag database to separate artists from other tags.

## This database is obtained by launching database.py:
![database.py](/img/PowerShell_2023-02-11_21_33_46.jpg)
```
usage: database.py [-h] [-p PROXY]
```
Optionally, you can use a proxy:
| Flag        | Description |
|-------------|-------------|
| `-p PROXY`, `--proxy PROXY`  | The proxy to use for all network calls. Usage examples: http://proxy.server:8888 or http://user:password@proxy.server:8888 |

> **Warning**
> database.py downloads around 1GB of data from https://e621.net/db_export/ each time it's run. There is no verification if any downloads are needed, files are updated regardless.

~7.5GB of free RAM is required to run it.  
Around 400MB of files will be written to disk as a result (trimmed databases `posts.parquet` and `artists.parquet`).  
You don't need to update them unless you want to tag files added to e621 since the last time you've updated the database.  
Tagger WILL NOT succeed without the correctly prepared databases in it's working folder.  
It will also fail to find any files uploaded to e621 after you've last updated the database via database.py.
