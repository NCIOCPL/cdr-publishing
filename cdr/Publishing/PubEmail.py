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
# Last Modified:    $Date: 2007-07-06 22:50:06 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/PubEmail.py,v $
# $Revision: 1.1 $
#
# $Id: PubEmail.py,v 1.1 2007-07-06 22:50:06 venglisc Exp $
# $Log: not supported by cvs2svn $
# *********************************************************************
import cdr, sys, os

PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')
emailDL    = 'EmailDL.txt'

# Read the list of email addresses to be notified
file      = open(os.path.join(PUBPATH, emailDL), 'r')
mailList  = file.read()
file.close()

# Send the message
receivers = mailList.split()
sender    = "operator@cips.nci.nih.gov"
subject   = sys.argv[1]
message   = """\
Automated Publishing Job Email Notification
%s""" % sys.argv[2]

x =  cdr.sendMail(sender, receivers, subject, message)

sys.exit(0)
