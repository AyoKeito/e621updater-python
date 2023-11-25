@echo off

if not exist .\venv\ (
    echo Creating virtual environment...
    mkdir venv
    python -m venv .\venv\
    call .\venv\Scripts\activate
    echo Installing required packages...
    .\venv\Scripts\python.exe -m pip install --upgrade pip
    .\venv\Scripts\pip.exe install -r requirements.txt
)

call .\venv\Scripts\activate
echo Downloading databases:
.\venv\Scripts\python.exe database.py -m
echo Running tagger:
.\venv\Scripts\python.exe tagger.py -f

pause
deactivate
exit