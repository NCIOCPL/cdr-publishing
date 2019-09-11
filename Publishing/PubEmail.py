#!d:/python/python.exe
# *********************************************************************
# Script to submit email notification as part of the automated
# publishing.
# ---------------------------------------------------------------------
# Created:          2007-04-03        Volker Englisch
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
LOGGER  = cdr.Logging.get_logger("PubEmail")
LOGGER.info('PubEmail Notification - Started')
LOGGER.info('Arguments: %s', sys.argv)

# Retrieve the Email addresses from the specified group
# -----------------------------------------------------
emailDL    = sorted(cdr.getEmailList('Operator Publishing Notification'))
emailDev   = sorted(cdr.getEmailList("Developers Notification"))

# Set the variables and send the message
# --------------------------------------
sender    = "NCIPDQoperator@mail.nih.gov"
subject   = "[%s] %s" % (cdr.Tier().name, sys.argv[1])
message   = """\
Automated Publishing Email Notification:

%s""" % sys.argv[2]

try:
    # Somebody needs to get the message if the group is empty
    if not len(emailDL):
        emailDL = emailDev
        subject = '*** DL Missing *** %s' % subject

    x =  cdr.sendMail(sender, emailDL, subject, message)
except:
    LOGGER.exception('*** Failure sending email message')
    raise

# All done, we can go home now
# ----------------------------
LOGGER.info('PubEmail Notification - Finished')
sys.exit(0)
