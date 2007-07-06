#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Control file to start the publishing scripts.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date: 2007-07-06 16:41:23 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/Jobmaster.py,v $
# $Revision: 1.1 $
#
# $Id: Jobmaster.py,v 1.1 2007-07-06 16:41:23 venglisc Exp $
# $Log: not supported by cvs2svn $
# *********************************************************************
import sys, re, string, os, shutil, cdr, getopt

# Setting directory and file names
# --------------------------------
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

UTIL       = os.path.join('d:\\cdr', 'Utilities')
LOGFILE    = 'Jobmaster.log'

testMode   = None
fullUpdate = None
backup     = True
istep      = 0

EmailError = 'oops'
CTGovError = 'oops'

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global fullUpdate
    global backup
    global l

    try:
        longopts = ["testmode", "livemode", "interim", "export",
                    "nobackup"]
        opts, args = getopt.getopt(args[1:], "btlie", longopts)
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
        elif o in ("-n", "--interim"):
            fullUpdate = False
            l.write("running in INTERIM mode")
        elif o in ("-e", "--export"):
            fullUpdate = True
            l.write("running in EXPORT mode")
        elif o in ("-b", "--nobackup"):
            backup = False
            l.write("running in NOBACKUP mode")

    if len(args) > 0:
        usage(args)
    if testMode is None:
        usage(args)
    if fullUpdate is None:
        usage(args)

    return


# ------------------------------------------------------------
# Function to display the default usage
# ------------------------------------------------------------
def usage(args):
    print args
    sys.stderr.write("""\
usage: %s [--livemode|--testmode] [--interim|--export] [--nobackup] [options]

options:
    -n, --interim
           running in interim (nightly) production mode

    -w, --export
           running in export (weekly) production mode

    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode

    -b, --nobackup
           run without creating a database backup file
""" % args[0].split('\\')[-1])
    sys.exit(1)

# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------

# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGFILE)
l.write('Jobmaster Publishing - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)

parseArgs(sys.argv)

# Setting the options for jobs which we are going to submit
# ---------------------------------------------------------
if testMode:
    runmode = '--testmode'
else:
    runmode = '--livemode'

if fullUpdate:
    pubmode = '--export'
else:
    pubmode = '--interim'

# Submit initial Notification that publishing started
# ---------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Initial Email' % istep, stdout = True)
    if fullUpdate:
        cmd = os.path.join(PUBPATH, 'SuccessEmail.py "%s" "%s"' % \
              ('Export Publishing Started',        # Subject
               'Export Job Started Successfully')) # Body
    else:
        cmd = os.path.join(PUBPATH, 'SuccessEmail.py "%s" "%s"' % \
              ('Interim Publishing Started',        # Subject
               'Interim Job Started Successfully')) # Body
    l.write('Submitting command...\n%s' % cmd, stdout = True)
    try:
        myCmd = cdr.runCommand(cmd)
        if myCmd.output:
            raise EmailError
    except EmailError:
        l.write('*** Error submitting email\n%s' % myCmd.output, 
                 stdout = True)
except:
    l.write('Sending Initial Email failed', stdout = True)
    sys.exit(1)

# Create the "Before" database snapshot
# -------------------------------------
if fullUpdate and backup:
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: Before DB Backup' % istep, stdout = True)
        cmd = os.path.join('d:\db_backup', 'BeforeSnapshot.bat')
        l.write('Submitting command...\n%s' % cmd, stdout = True)
        l.write('*** FIX ME ***', stdout = True)
        #try:
        #    myCmd = cdr.runCommand(cmd)
        #    if myCmd.output:
        #        raise EmailError
        #except EmailError:
        #    l.write('*** Error submitting email\n%s' % myCmd.output, 
        #             stdout = True)
    except:
        l.write('Creating Before DB Backup failed', stdout = True)
        sys.exit(1)

# Start the publishing job and FTP the data 
# -----------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Submit Pub Job' % istep, stdout = True)
    cmd = os.path.join(PUBPATH, 'SubmitPubJob.py %s %s' % (runmode, pubmode))

    l.write('Submitting command...\n%s' % cmd, stdout = True)

    myCmd = cdr.runCommand(cmd)
    
    print "Code: ", myCmd.code
    print "Outp: ", myCmd.output.find('Failure')
    print "--------------"
    if myCmd.code or myCmd.output.find('Failure') > 0:
        l.write('*** Error submitting command:\n%s' % myCmd.output, 
                 stdout = True)
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
          ('*** Error in SubmitPubJob.py', 
           'Program returned with error code.  Please see logfile.'))
        myCmd = cdr.runCommand(cmd)
        raise

except:
    l.write('Submitting Publishing Job failed', stdout = True)
    sys.exit(1)

# Start the copy of vendor data to CIPSFTP
# Only needed for export publishing
# ----------------------------------------
if fullUpdate:
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: FtpExportData Job' % istep, stdout = True)
        cmd = os.path.join(PUBPATH, 'FtpExportData.py %s %s' % (runmode, 
                                                                pubmode)) 

        l.write('Submitting command...\n%s' % cmd, stdout = True)
        myCmd = cdr.runCommand(cmd)

        if myCmd.code:
            l.write('*** Error submitting command:\n%s' % myCmd.output,
                     stdout = True)
            l.write('Code: %s' % myCmd.code, stdout = True)
            cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
              ('*** Error in FtpExportData.py', 
               'Program returned with error code.  Please see logfile.'))
            myCmd = cdr.runCommand(cmd)
            raise
    except:
        l.write('Submitting FtpExportData Job failed', stdout = True)
        sys.exit(1)


# Start the CTGovExport job and FTP the data
# ------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: CTGovExport Job' % istep, stdout = True)
    cmd = os.path.join(UTIL, 
                       'CTGovExport.py --optimize --maxtest 100 %s' %  runmode)

    l.write('Submitting CTGovExport Job...\n%s' % cmd, stdout = True)
    myCmd = cdr.runCommand(cmd)

    if myCmd.code:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
          ('*** Error in CTGovExport.py', 
           'Program returned with error code.  Please see logfile.'))
        myCmd = cdr.runCommand(cmd)
        raise
except:
    l.write('Submitting CTGovExport Job failed', stdout = True)
    sys.exit(1)


# Start the FtpCTGovData job to copy the data
# -------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: FTP CTGovExport Job' % istep, stdout = True)
    cmd = os.path.join(PUBPATH, 'FtpCTGovData.py %s' % runmode)

    l.write('Submitting command...\n%s' % cmd, stdout = True)
    myCmd = cdr.runCommand(cmd)

    if myCmd.code:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' \
          ('*** Error in FtpCTGovData.py', 
           'Program returned with error code.  Please see logfile.'))
        myCmd = cdr.runCommand(cmd)
        raise
except:
    l.write('Submitting FtpCTGovData Job failed', stdout = True)
    sys.exit(1)


# Send final Notification that publishing finished
# ------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Jobmaster Job Complete notification' % istep, 
                                                           stdout = True)
    if fullUpdate:
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
         ('Export Publishing Finished', 
          'Export Job Finished Successfully'))
    else:
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
         ('Interim Publishing Finished', 
          'Interim Job Finished Successfully'))
    l.write('Submitting command...\n%s' % cmd, stdout = True)
    try:
        myCmd = cdr.runCommand(cmd)
        if myCmd.output:
            raise EmailError
    except EmailError:
        l.write('*** Error submitting email\n%s' % myCmd.output,
                 stdout = True)
except:
    l.write('Submitting Final Email failed', stdout = True)
    sys.exit(1)

# Send Error Notification
# -----------------------

l.write('Jobmaster Publishing - Finished', stdout = True)
sys.exit(0)
