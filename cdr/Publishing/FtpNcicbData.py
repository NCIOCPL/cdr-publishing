#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Create a tar file of the latest publishing Terminology output 
# directory for the NCICB (Smita) and copy to the FTP server.
# This Terminology file contains slightly different data than the 
# licensee data.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2009-03-06        Volker Englisch
# Last Modified:    $Date: 2009-03-26 20:11:37 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/FtpNcicbData.py,v $
# $Revision: 1.2 $
#
# $Id: FtpNcicbData.py,v 1.2 2009-03-26 20:11:37 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.1  2009/03/26 19:35:40  venglisc
# Initial copy of program to ftp the NCICB data to the FTP server. (Bug 4497)
#
#
# *********************************************************************
import os, sys, cdr, optparse, ftplib, time, glob

OUTPUTPATH = cdr.BASEDIR + "/Output"
EXPORTPATH = OUTPUTPATH + "\\LicenseeDocs"
TARCMD     = "d:\\cygwin\\bin\\tar.exe"
FTPDIR     = 'd:\\cdr\\Output\\FtpSpecial'
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
TARGZ      = '.tar.gz'
LOGFILE    = 'Jobmaster.log'

FTPSERVER  = 'cipsftp.nci.nih.gov'
FTPUSER    = 'cdrdev'
FTPPWD     = '***REMOVED***'
FTPLOCK    = 'sending'

DATASETS   = {'NCICB' : 'Terminology'}

# Setting directory and file names
# --------------------------------
dateStr    = time.strftime("%Y-%m-%d-%H%M", time.localtime())
testMode   = None
fullMode   = None
outputOk   = True
zipIt      = True

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArguments(args):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    usage = "usage: %prog [--livemode | --testmode] [options]"
    parser = optparse.OptionParser(usage = usage)

    parser.set_defaults(testMode = True)
    parser.set_defaults(fullMode = True)
    parser.add_option('-t', '--testmode',
                      action = 'store_true', dest = 'testMode',
                      help = 'running in TEST mode')
    parser.add_option('-l', '--livemode',
                      action = 'store_false', dest = 'testMode',
                      help = 'running in LIVE mode')
    parser.add_option('-f', '--export',
                      action = 'store_true', dest = 'fullMode',
                      help = 'running in TEST mode')
    parser.add_option('-i', '--interim',
                      action = 'store_false', dest = 'fullMode',
                      help = 'running in LIVE mode')

    # Exit if no command line argument has been specified
    # ---------------------------------------------------
    if len(args[1:]) == 0:
        parser.print_help()
        sys.exit('No arguments given!')

    (options, args) = parser.parse_args()
    # Read and process options, if any
    # --------------------------------
    if parser.values.testMode:
        l.write("Running in TEST mode", stdout = True)
    else:
        l.write("Running in LIVE mode", stdout = True)

    if parser.values.fullMode:
        l.write("Running in EXPORT mode", stdout = True)
    else:
        l.write("Running in INTERIM mode", stdout = True)

    return parser
    

# ------------------------------------------------------------
# Function to display the default usage
# ------------------------------------------------------------
def usage(args):
    print args
    sys.stderr.write("""\
usage: %s [options]

options:
    -f, --ftponly
           the tar files already exist, don't need to recreate them.
           This will only ftp the files

    -n, --interim
           running in interim production mode

    -w, --export
           running in export production mode

    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode
""" % sys.argv[0].split('\\')[-1])

    sys.exit(1)


# ------------------------------------------------------------
# Function to create a tar archive to be copied to the FTP
# server
# ------------------------------------------------------------
def createArchive(filename, dir):
     tarFile  = filename + TARGZ
     l.write("Creating tar file %s ..." % tarFile, stdout=True)
     
     if not os.path.isdir(FTPDIR):
         l.write("Creating directory %s" % FTPDIR, stdout=True)
         os.makedirs(FTPDIR)

     # Can't use FTPDIR for the tarPath because the cygwin tar command
     # sees the drive letter D: as a host name.
     ### tarPath  = '/cdr/Output/FtpSpecial'
     ### tarPath  = os.path.join(tarPath, tarFile)
     os.chdir(FTPDIR)
     print 
     print 'dir = %s' % dir
     outFile  = os.popen('%s --directory %s --create --gzip --file %s %s 2>&1' %
                                        (TARCMD, OUTPUTPATH, tarFile, dir))
     output   = outFile.read()
     result   = outFile.close()
     if result:
         l.write("  tar return code: %d" % result, stdout=True)
         l.write("*** Exiting.", stdout = True)
         return 1 

     if output:
         l.write("%s" % output, stdout=True)

     return 0 


# ------------------------------------------------------------
# Function to remove duplicate list elements from a given list
# ------------------------------------------------------------
def removeDups(list):
    result = []
    for item in list:
        if item not in result:
            result.append(item)
    return result

# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------

# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGFILE)
l.write('FtpOtherData - Started',   stdout = True)
l.write('Arguments: %s' % sys.argv, stdout = True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
fullMode  = options.values.fullMode
print ''

os.chdir(OUTPUTPATH)

try:
    # Find the last publishing output directory Job????
    # -------------------------------------------------------------
    l.write("Searching for latest publishing directory ...", stdout=True)
    lastDir  = glob.glob('Job????')
    lastDir.sort()
    lastDir.reverse()
    lastDir = lastDir[0]
    l.write("  %s found" % lastDir, stdout = True)

    for org in DATASETS.keys():
        path = '%s/%s' % (lastDir, DATASETS[org])

        if not os.access(path, os.F_OK):
            l.write("*** Invalid path ***", stdout = True)
            l.write("    %s" % path,        stdout = True)
            sys.exit("Error reading data")

        # Go through the directories and create the tar files
        # ---------------------------------------------------
        if zipIt:
            # The special licensee data will now be zipped
            # ----------------------------------------------------
            if testMode:
                ftpDir = "%s\Test" % FTPDIR
            else:
                ftpDir = FTPDIR

            l.write("Creating tar file for %s ..." % lastDir, stdout = True)
            os.chdir(lastDir)

            orgDoctypeName = '%s_%s_%s' % (lastDir, org, DATASETS[org])

            if testMode:
                orgDoctypeName += '.test'
            result = createArchive(orgDoctypeName, path)
        
            if result:
                l.write("*** Error creating %s tar file ***" % lastDir,
                         stdout = True)
                l.write("*** Output for %s not in Licensee directory" % lastDir,
                         stdout = True)
                sys.exit(1)
            print "Creating tar file... Done.\n"


    # Setting path variables for FTP server
    # -------------------------------------
    os.chdir(PUBPATH)
    if testMode:
        if fullMode:
           ftpDir   = '/u/ftp/test/ncicb/incoming/full'
        else:
           ftpDir   = '/u/ftp/test/ncicb/incoming/partial'
    else:
        if fullMode:
           ftpDir   = '/u/ftp/qa/ncicb/incoming/full'
        else:
           ftpDir   = '/u/ftp/qa/ncicb/incoming/partial'

    l.write("Copy files to FTP server", stdout=True)
    l.write("Remote dir: %s" % ftpDir, stdout=True)

    # Create the connection to the FTP server
    # ---------------------------------------
    try:
        ftp = ftplib.FTP(FTPSERVER)
        ftp.login(FTPUSER, FTPPWD)
        chCwd = ftp.cwd(ftpDir)
        l.write("%s" % chCwd, stdout = True)
        os.chdir(FTPDIR)

        # Locking any processing on CIPSFTP
        # ---------------------------------
        ftp.rename(FTPLOCK, FTPLOCK + '.lck')

        for org in DATASETS.keys():
            # In case there are newlines in the lockfile, skip those
            # ------------------------------------------------------
            if org == '':
                continue

            ftpFile = '%s%s' % (orgDoctypeName, TARGZ)
            l.write("Transfer file %s..." % ftpFile, stdout = True)
            ftp.storbinary('STOR %s' % ftpFile, open(ftpFile, 'rb'))
            l.write("Bytes transfered %d" % ftp.size(ftpFile))

        # Unlocking processing on CIPSFTP
        # -------------------------------
        ftp.rename(FTPLOCK + '.lck', FTPLOCK)

    except ftplib.Error, msg:
        l.write('*** FTP Error ***\n%s' % msg, stdout = True)
        sys.exit(1)

    l.write('FtpOtherData - Completed', stdout = True)

except SystemExit, info:
    l.write("SystemExit: %s" % info, stdout = True)
    raise
except Exception, arg:
    l.write('*** Error - %s' % arg, stdout = True)
except:
    l.write('*** Error - Unexpected failure', stdout=True)

sys.exit(0)
