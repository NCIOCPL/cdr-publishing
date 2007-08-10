#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Script to submit email notification as part of the automated 
# publishing.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date: 2007-08-10 16:38:25 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/PubEmail.py,v $
# $Revision: 1.2 $
#
# $Id: PubEmail.py,v 1.2 2007-08-10 16:38:25 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.1  2007/07/06 22:50:06  venglisc
# Initial copy of MFP scheduling scripts.
#
# *********************************************************************
import cdr, sys, os, os.path

# Check for the two mandatory command line arguments
# --------------------------------------------------
if len(sys.argv) < 3:
    sys.stderr.write("\nusage:  %s subject message\n" % os.path.basename(
                                                           sys.argv[0]))
    sys.exit(1)

# Open Log file and enter start message
# -------------------------------------
LOGFILE    = 'PubEmail.log'
l = cdr.Log(LOGFILE)
l.write('PubEmail Notification - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)

# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
emailDL    = 'EmailDL.txt'

# Read the list of email addresses to be notified
# -----------------------------------------------
file      = open(os.path.join(PUBPATH, emailDL), 'r')
mailList  = file.read()
file.close()

# Set the variables and send the message
# --------------------------------------
receivers = mailList.split()
sender    = "operator@cips.nci.nih.gov"
subject   = "%s: %s" %(cdr.PUB_NAME.capitalize(), sys.argv[1])
message   = """\
Automated Publishing Email Notification:

%s""" % sys.argv[2]

try:
    x =  cdr.sendMail(sender, receivers, subject, message)
    l.write('No errors', stdout = True)
except:
    l.write('*** Error:\n%s' % str(x), stdout = True)
    raise

# All done, we can go home now
# ----------------------------
l.write('PubEmail Notification - Finished', stdout = True)
sys.exit(0)
