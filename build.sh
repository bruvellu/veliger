#!/bin/bash

# From scratch:
#
#   Install ActivePython using Wine:
#
#       wine msiexec /i python2.7.1.msi
#
#   Install pywin, pyexiv2, PIL, and PyQt:
#
#       wine pywin.exe (etc)
#
#   Install requests:
#
#       python.exe setup.py install (etc)


PIDIR="/home/nelas/src/pyinstaller-2.0"
VERSION=`grep "^__version__" veliger.py | cut -d "'" -f 2`
FOLDER="./pyinstaller/$VERSION"

# Check if folder exists
if [ -d "$FOLDER" ]; then
    rm -r $FOLDER
fi

# Make folder
mkdir $FOLDER

# Make spec file without --onefile, it gives an error on windows
/home/nelas/.wine/drive_c/Python27/python.exe $PIDIR/pyinstaller.py --onefile -o $FOLDER veliger.py

# Build spec file
/home/nelas/.wine/drive_c/Python27/python.exe $PIDIR/pyinstaller.py $FOLDER/veliger.spec

# Copy Mendeley keys
#cp mendeley_api_keys.pkl $FOLDER/dist/veliger/

# Copy executable to new folder, zip it and send to Dropbox
cd $FOLDER
cp -r dist veliger_v$VERSION
zip -r -9 veliger_exe veliger_v$VERSION
mv veliger_exe.zip veliger_v$VERSION.zip
cp veliger_v$VERSION.zip /home/nelas/Dropbox/CEBIMar/
