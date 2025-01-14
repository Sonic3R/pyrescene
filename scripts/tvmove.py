#!/usr/bin/env python3
# -*- coding: latin-1 -*-

"""
Show the possible parameters and usage:
    python TVMove.py --help

Created on 25-jul-2009

Tested on Windows with cygwin.

What does it do? It changes this:
    .
    |-- 24.S07E01.DVDRip.XviD-TOPAZ
    |-- 24.S07E02.DVDRip.XviD-TOPAZ
    |-- 24.S07E03.DVDRip.XviD-TOPAZ
    |-- tpz-24701-sample.avi
    |-- tpz-24701.nfo
    |-- tpz-24702-sample.avi
    |-- tpz-24702.nfo
    |-- tpz-24703-sample.avi
    `-- tpz-24703.nfo

to this:
    .
    |-- 24.S07E01.DVDRip.XviD-TOPAZ
    |   |-- Sample
    |   |   `-- tpz-24701-sample.avi
    |   `-- tpz-24701.nfo
    |-- 24.S07E02.DVDRip.XviD-TOPAZ
    |   |-- Sample
    |   |   `-- tpz-24702-sample.avi
    |   `-- tpz-24702.nfo
    `-- 24.S07E03.DVDRip.XviD-TOPAZ
        |-- Sample
        |   `-- tpz-24703-sample.avi
        `-- tpz-24703.nfo

This program is useful for:
  - moving srt subtitles into their corresponding directory.
  - moving downloaded television series to their correct scene folder.
    (if your usenet client doesn't do this already for you, like Pan)
    You must create the folders separately. e.g. by a batch script:
       mkdir folder_name1
       mkdir ...
    Save it as make_dirs.bat.
    Execute it: ./make_dirs.bat and you have your dirs.
    
    Do it fast with vim, based on nzb/par2 file names:
        ls -1 *.nzb > mkdir.bat
        vim mkdir
            q a i mkdir <ESC> j 0 q    record a macro
            10@a                       execute it 10 times
            :%s/.nzb//g                remove the extensions
            :wq                        save and quit
    
  - learning Python. This is my very first Python program!

Example usage: ./TVMove.py -s .
If you get     bash: ./TVMove.py: Permission denied
do             chmod u+x TVMove.py

Place this in your bin dir to use your own name and options:
    #!/bin/bash
    exec python /home/you/bin/TVMove.py -s . $@
Name the file 'tvmove' and you can use 'tvmove' like it would be 
any other command. Make it executable:
    chmod u+x tvmove

To create your own bin dir for executable files:
* Create the dir:
    mkdir ~/bin
* To add a directory to your PATH, add
    #my own executable files
    PATH=$PATH:$HOME/bin
  to your .bashrc file

http://motechnet.com/~gfy/tvmove/

TODO:
-----
make these work:
    The.Genius.of.Photography.E01.Fixing.the.Shadows.DVDRiP.XViD-DeBTV
    debt-tgop.e01.English.srt
    
    No folder found for 30.rock.508.720p-dimension.sample.srs
    No folder found for off.the.map.110.720p-dimension.sample.srs
	
Moving... The.Unit.S02E02.RARFIX.DVDRip.XviD-TOPAZ.srr to
          The.Unit.S02E02.RARFIX.DVDRip.XviD-TOPAZ\
[Error 183] Kan geen bestand maken dat al bestaat Exiting...
-> Make it skip and continue + error report

Make sure that files that need moving aren't in the root dir:
tvmove ./subs -n
relative to current working directory

With multiple possibilities, try to gues the right one, not the first one:
The.Unit.S02E02.DVDRip.XviD-TOPAZ
The.Unit.S02E02.RARFIX.DVDRip.XviD-TOPAZ

Support for PartX episodes.

http://stackoverflow.com/questions/1471153/string-similarity-metrics-in-python

Separate algorithm from the files and add unit tests.
http://www.machinalis.com/blog/separate-io-from-algorithms/

0.5: move proof files to its folder, better detection due to x264 (2016-06-25)
0.4: extra's, files like fs1001uc.xvid-siso.nfo work (2009-10-15)
     wat-himym-s02e01-sample.avi gets recognized now
0.3: support for subpacks (2009-08-21)
0.2: refactorings, additional comments (2009-07-27)
0.1: initial release (2009-07-26)

@author: Gfy
"""

import os, sys, glob, re, optparse

__VERSION__ = "0.5"

# a dictionary with key/value pairs
folders = {}

def send_error(message):
    print("%s Exiting..." % message)
    sys.exit(1)

# adds a release directory to the folders variable
def append_folder(key, value):
    global folders
    folders[key] = value

def get_key(name):
    '''
    This function tries to generate a unique identifying key for a given
    release name or file name.
    '''

    # for folders
    patternRegular = ".*[\.-]?[sS]([0-9]?[0-9])[\.]?[eE]([0-9]{1,3})[\.-]?[eE]?([0-9]{2,3})?.*"
    patternFoV = ".*\.?([0-9]{1,2})[x]([0-9]{2,3})([\._-]([0-9]{1,2}[x])?)?([0-9]{2,3})?[\._]?.*"
    patternRETRO = ".*\.[eE][pP]([0-9][0-9]).*"

    # for files like:
    #     tpz-24724.nfo 24.S07E24.PREAIR.DVDRip.XviD-TOPAZ
    #     fs1001uc.xvid-siso.nfo Friends.S10E01.UNCUT.DVDRip.XviD-SiSO
    #     leverage.113.dvdrip.xvid-saints.nfo
    patternFile = ".*(?:(?:[0-9][0-9])([0-9]+)|[^0-9]([0-9]{1,2}))([0-9]{2})\.?.*"
    
    # filter out known false positives causing trouble for detection
    # e.g. sample-veronica.mars.101.dvdrip.x264-mm.mkv
    name = name.replace("x264", "")
    name = name.replace("h264", "")
    name = name.replace("x265", "")
    name = name.replace("h265", "")

    # test if it's a release folder
    regular_match = re.match(patternRegular, name)
    fov_match = re.match(patternFoV, name)  # TODO: x264 could be valid here
    retro_match = re.match(patternRETRO, name)

    # test for the TOPAZ file format
    file_match = re.match(patternFile, name)

    subpack_match = re.search("subpack", name, re.IGNORECASE)
    extras_match = re.search("extras", name, re.IGNORECASE)
    match = False

    if regular_match:
        match = True
        season = int(regular_match.group(1))
        episode = int(regular_match.group(2))
    elif fov_match:
        match = True
        season = int(fov_match.group(1))
        episode = int(fov_match.group(2))
    elif file_match:
        match = True
        if file_match.group(1) == None:
            season = int(file_match.group(2))
        else:
            season = int(file_match.group(1))
        episode = int(file_match.group(3))
    elif not match and retro_match:
        match = True
        season = 1
        episode = int(file_match.group(1))
    elif not match and subpack_match:
        match = True
        season = 999
        episode = 999
    elif not match and extras_match:
        match = True
        season = 999
        episode = 998

    if match:
        # construct a key: ssseee
        return '%(season)03d%(episode)03d' % {'season': season, "episode": episode}

    return None

def check_new_folder(foldername):
    key = get_key(foldername)
    if key is not None:
        if options.verbose > 1:
            print("Release folder found: " + str(foldername.strip(os.sep)))
            print("    Season: " + str(int(key[:3])))  # The first three characters
            print("    Episode: " + str(int(key[3:])))  # All but the first three characters
            print("    Generated key: " + key)

        # add to the list of folders
        append_folder(key, foldername)

def check_for_subdir(file):
    extra_subdir = ""

    # does it needs to be moved to a Sample/Subs dir?
    if options.samples_subs:
        if re.search("sample", file, re.IGNORECASE):
            extra_subdir = "Sample"
        elif re.search("subs|vobsub", file, re.IGNORECASE):
            extra_subdir = "Subs"

    if options.proofs:
        if re.search("proof.*.jpg", file, re.IGNORECASE):
            extra_subdir = "Proof"

    if options.verbose > 1 and extra_subdir != "":
        print("Will be moved to additional subdir %s." % extra_subdir)

    return extra_subdir

def move_file(move_to_folder, file):
    extra_subdir = check_for_subdir(file)

    if options.verbose > 0:
        print("Moving... %(file)s to\n          %(dir)s" %
            {'file': os.path.basename(file),
             'dir': move_to_folder + extra_subdir})

    if not options.dry_run:
        if options.verbose > 1:
            print("Actually moving the file.")

        try:
            move_to_folder = os.path.realpath(move_to_folder + os.sep +
                                              extra_subdir + os.sep + file)
            file = os.path.realpath(file)
            os.renames(file, move_to_folder)
        except (IOError, os.error) as err:
            send_error(err)

def main(options, args):
    count_directories = 0
    count_files = 0

    # iterate the directories to process
    for path in args:
        try:
            os.chdir(path)
        except:
            send_error("Can't enter %s." % path)

        if options.verbose > 0:
            print("### Processing %s ###" % 
				os.path.realpath(os.path.basename(path)))

        # clean dictionary
        global folders
        folders = {}

        # iterate through all the folders in given directory
        for folder in glob.glob("*" + os.sep):
            # process the folder
            check_new_folder(folder)
        if options.verbose > 0:
            print("### %d episode folders found. ###" % len(folders))
        elif options.verbose > 1:
            for (key, value) in folders.items():
                print(key + " " + value.rstrip(os.sep))

        # iterate through all the files in given directory
        for file in os.listdir(os.curdir):
            # only process files, not directories
            if os.path.isfile(file):
                # retrieve episode and season
                key = get_key(file)

                if key is not None:
                    if options.verbose > 1:
                        print("Key found for file %(file)s: %(key)s" % 
							{'file': file, "key": key})

                    # check if there is a folder to move to
                    if key in folders:
                        count_files += 1
                        move_file(folders[key], file)

                    else:
                        if options.verbose > 0:
                            print("No folder found for %s" % file)

                # season and episode can't be detected
                else:
                    if options.verbose > 1:
                        print("Failed recognition for %(file)s" % {'file': file})

        count_directories += 1
    return (count_directories, count_files)

if __name__ == '__main__':
    parser = optparse.OptionParser(
        usage="Usage: %prog [options] dir1 ...",
        version="%prog " + __VERSION__)  # --help, --version

    bold = "\033[1m"
    reset = "\033[0;0m"

    output = optparse.OptionGroup(parser, "Feedback options")
    parser.add_option_group(output)

    output.add_option("-q", "--quiet",
                      action="store_const", const=0, dest="verbose",
                      help="don't print status messages to stdout")
    output.add_option("-v", "--verbose",
                      action="store_const", const=1, dest="verbose", default=1,
                      help="print feedback (default)")
    output.add_option("-y", "--noisy",
                      action="store_const", const=2, dest="verbose",
                      help="print internal workings too")

    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do no harm")
    parser.add_option("-s", "--sample-subs",
                      action="store_true", dest="samples_subs", default=False,
                      help="moves the detected " + bold + "sample" + reset +
                      " and " + bold + "subs" + reset +
                      " files respectively to ./Sample and ./Subs subdirs")
    parser.add_option("-p", "--proofs",
                      action="store_true", dest="proofs", default=False,
                      help="moves the proof image files to ./Proof subdirs")

    # no arguments given
    if len(sys.argv) < 2:
        print(parser.format_help())
    else:
        (options, args) = parser.parse_args()

        if options.verbose > 1:
            print("options: " + str(options))
            print("folders: " + str(args))

        (nb_dirs, nb_files) = main(options, args)

        if options.verbose > 0:
            print("All done.")
            print("Moved %d files when processing %s director%s" %
                    (nb_files, nb_dirs, "y." if (nb_dirs == 1) else "ies."))
