#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Control file to start the publishing scripts.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date: 2007-11-14 19:38:09 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/Jobmaster.py,v $
# $Revision: 1.6 $
#
# $Id: Jobmaster.py,v 1.6 2007-11-14 19:38:09 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.5  2007/09/07 22:29:53  venglisc
# Removed backup option.
#
# Revision 1.4  2007/08/22 00:50:04  venglisc
# Added code to only run the CTGovExport creation on Wednesdays and
# Fridays per NLM request.
#
# Revision 1.3  2007/08/14 00:04:40  venglisc
# Final version of Jobmaster.py.  For production the NightlyRefresh
# to update the CDR database on FRANCK has been removed.
#
# Revision 1.2  2007/08/10 16:44:37  venglisc
# Finalized initial version of submission program.
#
# Revision 1.1  2007/07/06 16:41:23  venglisc
# Initial copy of Jobmaster script used to run all nightly publishing
# steps for MFP.
#
# *********************************************************************
import sys, re, string, os, shutil, cdr, getopt, time

# Setting directory and file names
# --------------------------------
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

UTIL       = os.path.join('d:\\cdr', 'Utilities')
LOGFILE    = 'Jobmaster.log'

weekDay    = time.strftime("%a")
testMode   = None
fullUpdate = None
refresh    = True
istep      = 0

EmailError = 'oops'
CTGovError = 'oops'

# ------------------------------------------------------------
# Function to parse the command line arguments
# Note:  testmode/livemode is currently only used to be passed
#        to the called program
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global fullUpdate
    global refresh
    global l

    try:
        longopts = ["testmode", "livemode", "interim", "export"]
        opts, args = getopt.getopt(args[1:], "tlie", longopts)
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
        elif o in ("-i", "--interim"):
            fullUpdate = False
            l.write("running in INTERIM mode")
        elif o in ("-e", "--export"):
            fullUpdate = True
            l.write("running in EXPORT mode")

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
usage: %s [--livemode|--testmode] [--interim|--export] [options]

options:
    -i, --interim
           running in interim (nightly) production mode

    -e, --export
           running in export (weekly) production mode

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


# Submit initial email notification to indicate process has started
# -----------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Initial Email' % istep, stdout = True)
    if fullUpdate:
        subject = 'Weekly Publishing Started'
        message = 'Weekly Job Started Successfully'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
    else:
        subject = 'Nightly Publishing Started'
        message = 'Nightly Job Started Successfully'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
    l.write('Submitting command...\n%s' % cmd, stdout = True)
    try:
        myCmd = cdr.runCommand(cmd)
        print "Code: ", myCmd.code
        print "Outp: ", myCmd.output.find('Failure')
        print "--------------"
        if myCmd.code or myCmd.output.find('Failure') > 0:
            raise EmailError
    except EmailError:
        l.write('*** Error submitting email\n%s' % myCmd.output, 
                 stdout = True)
        raise
except:
    l.write('Sending Initial Email failed', stdout = True)
    sys.exit(1)

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
        subject = '*** Error in SubmitPubJob.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
        myCmd   = cdr.runCommand(cmd)
        raise

except:
    l.write('Submitting Publishing Job failed', stdout = True)
    sys.exit(1)

# FTP the publishing data (Vendor output) to CIPSFTP
# Note: Step only needed for weekly publishing
# --------------------------------------------------
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
            subject = '*** Error in FtpExportData.py'
            message = 'Program returned with error code.  Please see logfile.'
            cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
            myCmd   = cdr.runCommand(cmd)
            raise
    except:
        l.write('Submitting FtpExportData Job failed', stdout = True)
        sys.exit(1)


# Create the CTGovExport data with every nightly job and the full export
# as part of the weekly (on Friday/Saturday).
# -------------------------------------------------------------------
# Create the CTGovExport data for NLM
# -----------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: CTGovExport Job' % istep, stdout = True)

    if fullUpdate:
        since = '--since="2000-01-01"'
        cmd = os.path.join(UTIL, 
                           'CTGovExport.py --optimize %s %s' %  (runmode,
                                                                 since))
    else:
        cmd = os.path.join(UTIL, 
                           'CTGovExport.py --optimize %s' %  runmode)
                         # 'CTGovExport.py --optimize --maxtest 100 %s' %  
                         #                                         runmode)
                         #   Specifying maxtest option for testing only
    
    l.write('Submitting CTGovExport Job...\n%s' % cmd, stdout = True)
    myCmd = cdr.runCommand(cmd)
    
    if myCmd.code:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        subject = '*** Error in CTGovExport.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
        myCmd   = cdr.runCommand(cmd)
        raise
except:
    l.write('Submitting CTGovExport Job failed', stdout = True)
    sys.exit(1)
    
    
# Ftp the FtpCTGovData to the CIPSFTP server
# ------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: FTP CTGov2Nlm Job' % istep, stdout = True)
    cmd = os.path.join(PUBPATH, 'FtpCTGov2Nlm.py %s' % runmode)
    
    l.write('Submitting command...\n%s' % cmd, stdout = True)
    myCmd = cdr.runCommand(cmd)
    
    if myCmd.code:
        l.write('*** Error submitting command:\n%s' % myCmd.output,
                 stdout = True)
        subject = '*** Error in FtpCTGov2Nlm.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' \
                                    (subject, message))
        myCmd = cdr.runCommand(cmd)
        raise
except:
    l.write('Submitting FtpCTGov2Nlm Job failed', stdout = True)
    sys.exit(1)


# Send final Notification that publishing on CDR servers has finished
# Note: More processing to be completed on Cancer.gov and CIPSFTP
# -------------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Jobmaster Job Complete notification' % istep, 
                                                           stdout = True)
    if fullUpdate:
        subject = 'Weekly Publishing Finished'
        message = 'Weekly Job Finished Successfully'
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                     (subject, message))
    else:
        subject = 'Nightly Publishing Finished'
        message = 'Nightly Job Finished Successfully'
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                    (subject, message))
    l.write('Submitting command...\n%s' % cmd, stdout = True)
    try:
        myCmd = cdr.runCommand(cmd)
        print "Code: ", myCmd.code
        print "Outp: ", myCmd.output.find('Failure')
        print "--------------"
        if myCmd.code or myCmd.output.find('Failure') > 0:
            raise EmailError
    except EmailError:
        l.write('*** Error submitting email\n%s' % myCmd.output,
                 stdout = True)
        raise
except:
    l.write('Submitting Final Email failed', stdout = True)
    sys.exit(1)

# All done, going home now
# ------------------------
l.write('Jobmaster Publishing - Finished', stdout = True)
sys.exit(0)
