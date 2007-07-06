#!d:/python/python.exe
# *******************************************************
# File Name:  SuccessEmail.py
#             ---------------
# Script to test the email module
# *******************************************************
import cdr, sys

receivers = ["***REMOVED***"]
sender    = "operator@cips.nci.nih.gov"
subject   = sys.argv[1]
message   = """\
Automated Publishing Job Email Notification
%s""" % sys.argv[2]

x =  cdr.sendMail(sender, receivers, subject, message)

sys.exit(0)
