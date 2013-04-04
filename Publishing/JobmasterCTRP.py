#!d:/python/python.exe
# *********************************************************************
#
# File Name: JobmasterCTRP.py
#            ================
# Control file to start the CTRP processing scripts.
# (Adapted from Jobmaster.py)
# ---------------------------------------------------------------------
# $Author: volker $
# Created:          2012-09-14        Volker Englisch
# Last Modified:    $Date: 2012-07-09 18:49:29 -0400 (Mon, 09 Jul 2012) $
#
# $Source: /usr/local/cvsroot/cdr/Publishing/Jobmaster.py,v $
# $Revision: 10467 $
#
# $Id: Jobmaster.py 10467 2012-07-09 22:49:29Z volker $
#
# BZIssue::4942 - [CTRP] Merge RSS site info from CTRP trials into
#                 CT.gov record
#
# *********************************************************************
import sys, os, cdr, getopt, time

# Setting directory and file names
# --------------------------------
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

UTIL       = os.path.join('d:\\cdr', 'Utilities')
UBIN       = os.path.join('d:\\cdr', 'Utilities', 'bin')
LOGFILE    = 'JobmasterCTRP.log'

weekDay    = time.strftime("%a")
testMode   = None
fullUpdate = None
istep      = 0

# ------------------------------------------------------------
# Function to parse the command line arguments
# Note:  testmode/livemode is currently only used to be passed
#        to the called program
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global fullUpdate
    global l

    try:
        longopts = ["testmode", "livemode"]
        opts, args = getopt.getopt(args[1:], "tl", longopts)
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
usage: %s [--livemode|--testmode]

options:
    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode

""" % sys.argv[0].split('\\')[-1])
    sys.exit(1)

# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------

# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGFILE)
l.write('JobmasterCTRP Publishing - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)

parseArgs(sys.argv)

# Setting the options for jobs which we are going to submit
# ---------------------------------------------------------
if testMode:
    runmode = '--test'
else:
    runmode = '--live'


# Submit initial email notification to indicate process has started
# -----------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Initial Email' % istep, stdout = True)
    subject = 'CTRP Protocol Processing Started'
    message = 'CTRP Protocol Processing Job Started Successfully'
    cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
    l.write('Submitting command...\n%s' % cmd, stdout = True)

    # cmd = 'ls'
    myCmd = cdr.runCommand(cmd, joinErr2Out = False)

    if myCmd.error:
        l.write('*** Error submitting email\n%s' % myCmd.error,
                 stdout = True)
        raise Exception
except:
    l.write('*** Error: Sending Initial Email failed', stdout = True)
    sys.exit(1)

try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Submit Download CTRP Trials Job' % istep, stdout = True)
    os.chdir(UBIN)
    cmd = os.path.join(UBIN, 'DownloadCtrpTrials.py')

    l.write('Submitting command...\n%s' % cmd, stdout = True)

    # cmd = 'ls'
    myCmd = cdr.runCommand(cmd)

    print "Code: ", myCmd.code
    print "Outp: ", myCmd.output.find('Error')

    # XXX Not sure if looking for 'Failure' is a reliable technique.
    if myCmd.code or myCmd.output.find('Error') > 0:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        subject = '*** Error in DownloadCtrpTrials.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
        # cmd = 'ls'
        myCmd   = cdr.runCommand(cmd)
        #raise Exception

except:
    l.write('*** Error: CTRP Download Job failed', stdout = True)
    sys.exit(1)

try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Submit Import CTRP Trials Job' % istep, stdout = True)
    cmd = os.path.join(UBIN, 'ImportCtrpSites.py %s' % runmode)

    l.write('Command temporarily disabled...\n%s' % cmd, stdout = True)
    l.write('Submitting command...\n%s' % cmd, stdout = True)

    # cmd = 'ls'
    myCmd = cdr.runCommand(cmd)

    print "Code: ", myCmd.code
    print "Outp: ", myCmd.output.find('Failure')

    if myCmd.code or myCmd.output.find('Failure') > 0:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        subject = '*** Error in ImportCtrpSites.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
        # cmd = 'ls'
        myCmd   = cdr.runCommand(cmd)
        #raise Exception

except:
    l.write('*** Error: CTRP Import Job failed', stdout = True)
    sys.exit(1)

# Send final Notification that publishing on CDR servers has finished
# Note: More processing to be completed on Cancer.gov and CIPSFTP
# -------------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Jobmaster Job Complete notification' % istep,
                                                           stdout = True)
    subject = 'CTRP Protocol Processing Finished'
    message = 'CTRP Protocol Processing Job Finished Successfully'
    cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                     (subject, message))
    l.write('Submitting command...\n%s' % cmd, stdout = True)

    # cmd = 'ls'
    myCmd = cdr.runCommand(cmd, joinErr2Out = False)

    if myCmd.error:
        l.write('*** Error submitting email\n%s' % myCmd.error,
                 stdout = True)
        raise Exception
except:
    # No need to interrupt the program if the email doesn't go out
    l.write('*** Error: Submitting Final Email failed', stdout = True)
    pass

# All done, going home now
# ------------------------
l.write('JobmasterCTRP - Finished', stdout = True)
sys.exit(0)
