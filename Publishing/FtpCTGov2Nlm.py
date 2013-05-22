#----------------------------------------------------------------------
# $Id$
#
# File Name: $RCSFile:$
#            ==============
# Submit the CTGovExport data to the NLM's FTP Server.
# 
# BZIssue::5167 - FTP Protocol Data to NLM Failing
#
#----------------------------------------------------------------------
import sys, cdr, os, glob, ftplib, time, getopt

# Setting directory and file names
# --------------------------------
LOGFILE    = 'FtpCTGov2Nlm.log'
dateStr    = time.strftime("%Y-%m-%d-%H%M", time.localtime())
FTPDIR     = os.path.join('d:\\cdr', 'Output', 'NLMExport')

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
def copyNlmFtpFile(localDirectory = 'd:/cdr/output/NLMExport', 
                   localFile      = 'study_collection.xml', 
                   ftpDirectory   = '/', 
                   ftpName        = 'clinical.txt'):

    FTPSERVER  = "clinftpp.nlm.nih.gov"
    FTPUSER    = "nci"
    FTPPWD     = "***REMOVED***"
    global testMode

    # Setting path variables for FTP server
    # -------------------------------------
    if testMode:
        l.write(' *** Warning ***', stdout = True)
        l.write(' Testmode needs to use paramiko in CBIIT environment',
                                                            stdout=True)
        l.write(' This is currently not implemented.', stdout=True)
        sys.exit(0)
        FTPSERVER  = "cipsftp.nci.nih.gov"
        FTPUSER    = "cdrdev"
        FTPPWD     = "***REMOVED***"
        ftpDir     = '/u/ftp/test/nlm/incoming'
    else:
        ftpDir     = ftpDirectory

    PUBDIR = localDirectory
    os.chdir(PUBDIR)

    # Creating the FTP command file
    # -----------------------------
    l.write("   LocalDir  = %s" % localDirectory, stdout = True)
    l.write("   localFile = %s" % localFile, stdout = True)
    l.write("   FTPDir    = %s" % ftpDir, stdout = True)
    l.write("   FTP Name  = %s" % ftpName, stdout = True)

    l.write("Copy files to ftp server", stdout = True)

    try:
        ftp = ftplib.FTP(FTPSERVER)
        ftp.login(FTPUSER, FTPPWD)

        # Don't change the directory on the NLM FTP
        # They sometimes throw you to the root instead of the login dir
        # -------------------------------------------------------------
        if not ftpDir == '/':
            chCwd = ftp.cwd(ftpDir)
            l.write("FTP: %s" % chCwd, stdout = True)
            l.write("FTPDIR: %s" % ftpDir, stdout = True)

        l.write("Transfer file %s..." % localFile, stdout = True)
        ftpFile = os.path.join(localDirectory, localFile)
        ftp.storbinary('STOR ' + localFile, open(ftpFile, 'rb'))
        l.write("Renaming file to %s" % ftpName, stdout = True)
        ftp.rename(localFile, ftpName)
        if ftpDir == '/':
            l.write("Bytes transfered %d" % ftp.size(ftpName), 
                                                   stdout = True)
        else:
            l.write("Bytes transfered %d" % ftp.size(ftpDir + '/' + ftpName), 
                                                   stdout = True)
    except ftplib.Error, msg:
        l.write('*** FTP Error ***\n%s' % msg, stdout=True)
        raise

    return

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global exportDir
    global l

    try:
        longopts = ["testmode", "livemode",
                    "dirname=", "logfile="]
        opts, args = getopt.getopt(args[1:], "tld:o", longopts)
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
usage: %s [--livemode|--testmode] [--dirname]

options:
    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode

    -d, --dirname 
           specify the directory name to be used for the file
           under \cdr\output\NLMExport
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
l.write('FtpCTGov2Nlm - Started', stdout=True)
l.write('Arguments: %s' % sys.argv, stdout=True)
                    
parseArgs(sys.argv)

# Setting the options for jobs which we are going to submit
# ---------------------------------------------------------
if testMode:
    runmode = '--testmode'
    l.write("Running in testmode")
else:
    runmode = '--livemode'
    l.write("Running in livemode")

try:
    if exportDir:
        l.write("Using specified Directory ...")
        l.write("DirName: %s" % exportDir)
        latestFile = getLatestFile(dirName = exportDir)
    else:
        l.write("Selecting Directory with latest timestamp...")
        latestFile = getLatestFile()

    lDir       = os.path.join(FTPDIR, latestFile[1])

    l.write("   Base Dir: %s" % FTPDIR, stdout = True)
    l.write("   Dir Name: %s" % latestFile[1], stdout = True)
    l.write("   Mod Time: %s\n" % time.strftime('%Y-%b-%d %H:%M:%S', 
                                        time.gmtime(latestFile[0])),
                                        stdout = True)

    doneFtp = copyNlmFtpFile(localDirectory = lDir)

except Exception, arg:
    l.write('*** Error - %s' % arg, stdout=True)
    raise
except:
    l.write('*** Program exists with failure', stdout=True)
    sys.exit(1)

l.write('FtpCTGov2Nlm - Completed', stdout=True)
sys.exit(0)
