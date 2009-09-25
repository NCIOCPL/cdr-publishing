#!d:/python/python.exe
# *******************************************************
# File Name:  ErrorEmail.py
#             ---------------
# Script to test the email module
# *******************************************************
import cdr, sys, socket, os.path

if len(sys.argv) < 3:
    sys.stderr.write("\nusage:  %s subject message\n" % os.path.basename(
                                                           sys.argv[0]))
    sys.exit(1)

localhost = socket.gethostname()
receivers = ["dackel@englisch.us"]
sender    = "operator@cips.nci.nih.gov"
subject   = "%s Error: %s" % (localhost.capitalize(), sys.argv[1])
message   = """\
   Failure processing Jobmaster step:
   %s""" % sys.argv[2]

x =  cdr.sendMail(sender, receivers, subject, message)

sys.exit(0)
