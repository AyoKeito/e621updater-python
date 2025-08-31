# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a Python-based e621 image tagging system with two main components:

- **database.py**: Downloads and processes e621 database exports (~1.1GB) into optimized parquet files
- **tagger.py**: Tags local images by matching MD5 hashes against the e621 database

The system works by:
1. Downloading e621 post data and tag classifications
2. Creating optimized parquet databases (posts.parquet, artists.parquet)
3. Matching local image files to e621 posts via MD5 hash or filename
4. Writing tags to image EXIF data or sidecar text files

## Common Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Windows batch script (creates venv, installs deps, runs both scripts)
start.bat
```

### Running Scripts

#### Database Update
```bash
# Basic database download/update
python database.py

# With multithreading (requires ~7.5GB RAM)
python database.py -m

# With proxy
python database.py -p http://proxy.server:8888
```

#### Image Tagging
```bash
# Write tags to EXIF data
python tagger.py -f

# Write tags to sidecar txt files
python tagger.py -t

# Specify folder path (otherwise uses GUI folder picker)
python tagger.py -f -p "C:\path\to\images"

# Don't rename files found by MD5 (prevents re-tagging)
python tagger.py -f -n
```

## Key Dependencies

- **pyexiftool**: Requires exiftool.exe in working directory (auto-downloaded)
- **modin/ray**: Optional multithreading for database operations
- **pyarrow**: Parquet file handling
- **aiohttp**: Async HTTP for database downloads

## Database Files

- `posts.parquet`: Main e621 post database with MD5 hashes and tags
- `artists.parquet`: Artist tag classifications
- `latest_posts.csv`: Temporary file during database processing (3GB)

The database must be updated via database.py before tagger.py can function. Files uploaded to e621 after the last database update won't be found.

## Architecture Notes

- Uses MD5 hash matching as primary identification method
- Falls back to filename matching if MD5 fails
- Supports both EXIF tagging and sidecar text file output
- GUI folder selection via tkinter when path not specified
- Async HTTP downloads with optional proxy support