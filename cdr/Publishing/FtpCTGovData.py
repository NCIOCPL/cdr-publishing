#----------------------------------------------------------------------
#
# File Name: $RCSFile:$
#            ==============
# Submit the CTGovExport data to the CIPSFTP Server.
# 
# $Id: FtpCTGovData.py,v 1.2 2007-08-10 16:50:15 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.1  2007/07/06 22:50:06  venglisc
# Initial copy of MFP scheduling scripts.
#
#----------------------------------------------------------------------
import sys, cdr, os, glob, ftplib, time, getopt

# Setting directory and file names
# --------------------------------
# PUBPATH    = os.path.join('d:\\cdr', 'publishing')
LOGFILE    = 'Jobmaster.log'
outDir     = os.path.join('d:\\cdr', 'Output', 'NLMExport')
dateStr    = time.strftime("%Y-%m-%d-%H%M", time.localtime())
tarName    = "clinical_trials.tar.bz2"
FTPSERVER  = "cipsftp.nci.nih.gov"
FTPDIR     = "d:\\cdr\\output\\NLMExport"
FTPUSER    = "cdrdev"
FTPPWD     = "***REMOVED***"
FTPLOCK    = "sending"

testMode   = None
exportDir  = None
rmDir      = 0
cdrDir     = 0
divider    = "=" * 60

# -------------------------------------------------------------------
# Function to find the directory name that was created last
# (Needs to be modified to allow passing the name)
# -------------------------------------------------------------------
def getLatestFile(baseDir = FTPDIR, dirName = None):
    """
    Function to get the last file or directory name created within
    the given directory
    - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    Input:  directory  -  name of directory to create a file listing
    Output: tupel of (timestamp, filename)
            timestamp (modification time) to be formatted for instance with
                   time.strftime('%Y-%b-%d %H:%M:%S', time.gmtime(tupel[0])
            filename string 
    """

    if dirName:
        files = [dirName]
    else:
        # files = os.listdir(baseDir) 
        # Only select files of the format 'YYYYMMDDHHmmSS'
        # ------------------------------------------------
        os.chdir(baseDir)
        files = glob.glob('2?????????????')

    # Create a list of tuples with the first element being the files
    # timestamp.  This allows us to sort the files in chronologic order
    # -----------------------------------------------------------------
    allFiles = []
    for filename in files:
        path = os.path.join(baseDir, filename)
        allFiles.append((os.stat(path)[-2], filename))

    allFiles.sort()
    return allFiles[-1]


# -------------------------------------------------------------------
# Function to create the file to ftp the CTGovExport data to the 
# FTP server.
# -------------------------------------------------------------------
def makeNlmFtpFile(localDirectory = 'd:/cdr/output/NLMExport', 
                   localFile      = 'clinical_trials.tar.bz2', 
                   ftpDirectory   = '/u/ftp/qa/nlm/incoming', 
                   ftpName        = 'clinical_trials.tar.bz2', 
                   compress       = 'Y'):

    global testMode

    # Setting path variables for FTP server
    # -------------------------------------
    if testMode:
        ftpDir  = '/u/ftp/test/nlm/incoming'
    else:
        ftpDir  = ftpDirectory

    PUBDIR = localDirectory
    os.chdir(PUBDIR)

    # Creating the FTP command file
    # -----------------------------
    l.write("  LocalDir  = %s" % localDirectory)
    l.write("  localFile = %s" % localFile)
    l.write("  FTPDir    = %s" % ftpDir)
    l.write("  FTP Name  = %s" % ftpName)

    l.write("Copy files to ftp server", stdout = True)
    try:
        ftp = ftplib.FTP(FTPSERVER)
        ftp.login(FTPUSER, FTPPWD)
        chCwd = ftp.cwd(ftpDir)
        l.write("FTP: %s" % chCwd, stdout = True)
        l.write("FTPDIR: %s" % ftpDir, stdout = True)

        ftp.rename(FTPLOCK, FTPLOCK + '.lck')
        l.write("Transfer file %s..." % localFile, stdout=True)
        ftp.storbinary('STOR ' + localFile, 
                            open(localDirectory + '\\' + localFile, 'rb'))
        l.write("Bytes transfered %d" % ftp.size(ftpDir + '/' + ftpName), 
                                                   stdout=True)
        ftp.rename(FTPLOCK + '.lck', FTPLOCK)
    except ftplib.Error, msg:
        l.write('*** FTP Error ***\n%s' % msg, stdout=True)
        raise

    return

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global l

    try:
        longopts = ["testmode", "livemode",
                    "dirname", "logfile"]
        opts, args = getopt.getopt(args[1:], "tldo", longopts)
    except getopt.GetoptError, e:
        usage(args)

    for o, a in opts:
        if o in ("-o", "--logfile"):
            global LOGFILE
            LOGFILE = a
            l = cdr.Log(LOGFILE)
        elif o in ("-t", "--testmode"):
            testMode = True
            l.write("running in TEST mode")
        elif o in ("-l", "--livemode"):
            testMode = False
            l.write("running in LIVE mode")
        elif o in ("-d", "--dirname"):
            exportDir = a
            l.write("running with directory name specified")

    if len(args) > 0:
        usage(args)
    if testMode is None:
        usage(args)

    return


# ------------------------------------------------------------
# Function to display the default usage
# ------------------------------------------------------------
def usage(args):
    print args
    sys.stderr.write("""\
usage: %s [--livemode|--testmode] [--nobackup]

options:
    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode

    -d, --dirname 
           specify the directory to be transferred    
           (default:  Ftp directory last created)

""" % sys.argv[0].split('\\')[-1])
    sys.exit(1)



# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------

# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l = cdr.Log(LOGFILE)
l.write('FtpCTGovData - Started', stdout=True)
l.write('Arguments: %s' % sys.argv, stdout=True)
                    
parseArgs(sys.argv)

# Setting the options for jobs which we are going to submit
# ---------------------------------------------------------
if testMode:
    runmode = '--testmode'
else:
    runmode = '--livemode'

try:
    if exportDir:
        print "Using specified Directory ..."
        latestFile = getLatestFile(dirName = exportDir)
    else:
        print "Selecting Directory with latest timestamp..."
        latestFile = getLatestFile()

    lDir       = os.path.join(outDir, latestFile[1])

    #print "Last File: ", latestFile
    l.write("   Base Dir:  %s" % FTPDIR, stdout = True)
    l.write("   File Name: %s" % latestFile[1], stdout = True)
    l.write("   Mod Time:  %s\n" % time.strftime('%Y-%b-%d %H:%M:%S', 
                                        time.gmtime(latestFile[0])),
                                        stdout = True)

    doneFtp = makeNlmFtpFile(localDirectory = lDir, compress = 'N')

except StandardError, arg:
    l.write('*** Error - %s' % arg, stdout=True)
    raise
except:
    l.write('*** Program exists with failure', stdout=True)
    sys.exit(1)

l.write('FtpCTGovData - Completed', stdout=True)
sys.exit(0)
