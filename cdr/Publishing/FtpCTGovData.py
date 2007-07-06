#----------------------------------------------------------------------
#
# File Name: $RCSFile:$
#            ==============
# Package and submit interim update documents (mid-month updates) to the 
# CIPSFTP server and store files in the directory cdr.
# The documents are located in subdirectories named JobNNN with NNN
# being an integer number.  Provide all jobIDs for the documents that 
# should be packaged within one subdirectory on the FTP server as a
# command line argument.
# For instance, if an interim update ran under JobID=1234 and an
# interim remove ran under JobID=1235 you want to package these 
# documents by entering the command
#     FtpInterimDocs.py 1234 1235
# 
# $Id: FtpCTGovData.py,v 1.1 2007-07-06 22:50:06 venglisc Exp $
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import sys, re, string, cdr, os, shutil, ftplib, time

# Setting directory and file names
# --------------------------------
log        = "d:\\cdr\\log\\Jobmaster.log" 
outDir     = os.path.join('d:\\cdr', 'Output', 'NLMExport')
pubDir     = os.path.join('d:\\cdr', 'publishing')
dateStr    = time.strftime("%Y-%m-%d-%H%M", time.localtime())
tarName    = "clinical_trials.tar.bz2"
FTPSERVER  = "cipsftp.nci.nih.gov"
FTPDIR     = "d:\\cdr\\output\\NLMExport"
FTPUSER    = "cdrdev"
FTPPWD     = "***REMOVED***"

testMode   = None
rmDir      = 0
cdrDir     = 0
divider    = "=" * 60

# -------------------------------------------------------------------
# Function to find the directory name that was created last
# (Needs to be modified to allow passing the name)
# -------------------------------------------------------------------
def getLatestFile(directory = FTPDIR):
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

    files = os.listdir(directory) 

    # Create a list of tuples with the first element being the files
    # timestamp.  This allows us to sort the files in chrononolic order
    # -----------------------------------------------------------------
    allFiles = []
    for filename in files:
        path = os.path.join(directory, filename)
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
    testMode = True

    # Setting path variables for FTP server
    # -------------------------------------
    if testMode:
        ftpDir  = '/u/ftp/qa/nlm/test/incoming'
    else:
        ftpDir  = ftpDirectory

    PUBDIR = localDirectory
    os.chdir(PUBDIR)

    # Creating the FTP command file
    # -----------------------------
    l.write("LocalDir  = %s" % localDirectory)
    l.write("localFile = %s" % localFile)
    l.write("FTPDir    = %s" % ftpDir)
    l.write("FTP Name  = %s" % ftpName)

    # os.chdir(pubDir)
    
    l.write("Copy files to ftp server", stdout=True)
    try:
        ftp = ftplib.FTP(FTPSERVER)
        ftp.login(FTPUSER, FTPPWD)
        chCwd = ftp.cwd(ftpDir)
        l.write("FTP: %s" % chCwd, stdout=True)

        l.write("Transfer file %s..." % localFile, stdout=True)
        ftp.storbinary('STOR ' + localFile, 
                            open(localDirectory + '\\' + localFile, 'rb'))
        l.write("Bytes transfered %d" % ftp.size(ftpDir + '/' + ftpName), 
                                                   stdout=True)
    except ftplib.Error, msg:
        l.write('*** FTP Error ***\n%s' % msg, stdout=True)
        sys.exit(1)

    return


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log('Jobmaster.log')
l.write('ftpCTGovData - Started', stdout=True)
                    
try:
    print "Selecting latest Directory ..."
    latestFile = getLatestFile()
    lDir       = os.path.join(outDir, latestFile[1])

    #print "Last File: ", latestFile
    l.write("File Name: %s" % latestFile[1], stdout=True)
    l.write("Mod Time:  %s" % time.strftime('%Y-%b-%d %H:%M:%S', 
                                        time.gmtime(latestFile[0] + 500000)),
                                        stdout=True)

    doneFtp = makeNlmFtpFile(localDirectory = lDir, compress = 'N')


except StandardError, arg:
    l.write('*** Error - %s' % arg, stdout=True)
except:
    l.write('*** Error - Unexpected failure', stdout=True)

l.write('ftpCTGovData - Completed', stdout=True)
sys.exit(0)
