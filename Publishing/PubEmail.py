#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Script to submit email notification as part of the automated 
# publishing.
# ---------------------------------------------------------------------
# $Author$
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date$
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/PubEmail.py,v $
# $Revision$
#
# $Id$
# $Log: not supported by cvs2svn $
# Revision 1.2  2007/08/10 16:38:25  venglisc
# Finished initial version of email notification script.
#
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

# Retrieve the Email addresses from the specified group
# -----------------------------------------------------
emailDL    = cdr.getEmailList('Operator Publishing Notification')
emailDL.sort()

# Set the variables and send the message
# --------------------------------------
sender    = "NCIPDQoperator@mail.nih.gov"
if cdr.h.org == 'OCE':
    subject   = "%s: %s" %(cdr.PUB_NAME.capitalize(), sys.argv[1])
else:
    subject   = "%s-%s: %s" %(cdr.h.org, cdr.h.tier, sys.argv[1])
message   = """\
Automated Publishing Email Notification:

%s""" % sys.argv[2]

try:
    # Somebody needs to get the message if the group is empty
    if not len(emailDL):
        emailDL = ['***REMOVED***']
        subject = '*** DL Missing *** %s' % subject

    x =  cdr.sendMail(sender, emailDL, subject, message)
except:
    l.write('*** Error:\n%s' % str(x), stdout = True)
    raise

# All done, we can go home now
# ----------------------------
l.write('PubEmail Notification - Finished', stdout = True)
sys.exit(0)
