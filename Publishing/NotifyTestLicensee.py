#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# We need to notify a new test licensee about the next steps once they
# have access to the data.  This program checks if a new Test Licensee
# had been added within the past two weeks and sends an internal 
# notification to submit the licensee notification, if applicable.
# ---------------------------------------------------------------------
# $Author$
# Created:          2009-12-07        Volker Englisch
# Last Modified:    $Date$
# 
# $Id$
# 
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib

OUTPUTBASE     = cdr.BASEDIR + "/Output/NLMExport"
WITHDRAWN_LIST = "WithdrawnFromPDQ.txt"
LOGNAME        = "CheckLicensees.log"
SMTP_RELAY     = "MAILFWD.NIH.GOV"
STR_FROM       = "PDQ Operator <operator@cips.nci.nih.gov>"
STR_TO         = "***REMOVED***"

now            = time.localtime(time.time())

testMode       = None
emailMode      = None
emailMode      = True

# Create an exception allowing us to break out if there are no new
# protocols found to report.
# ----------------------------------------------------------------
class NothingFoundError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


# --------------------------------------------------------------------
# Module to submit an email message if the program fails
# --------------------------------------------------------------------
def sendErrorMessage(msg, recipient = STR_TO):
    # We want to send an email so that the query doesn't silently fail
    # ----------------------------------------------------------------
    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, recipient, cdr.PUB_NAME.capitalize(),
       '*** Error: Program NotifyTestLicensee failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running NotifyTestLicensee.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, recipient, message.encode('utf-8'))
    server.quit()


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("NotifyTestLicensee - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

try:
    # Connect to the database to get the reason for withdrawl
    # -------------------------------------------------------
    conn = cdrdb.connect()
    cursor = conn.cursor()
    
    # Query the database with the information that needs to
    # be reported.
    # -----------------------------------------------------
    try:
        cursor.execute("""\
 SELECT d.id, d.title, q.value, 
        DATEDIFF(day, q.value, getdate()) as "DIFF"
   FROM document d
   JOIN query_term q
     ON q.doc_id = d.id
    AND q.path = '/Licensee/LicenseeInformation' +
                 '/LicenseeStatusDates/TestActivation'
  WHERE DATEDIFF(day, q.value, getdate()) <= 14
    AND DATEDIFF(day, q.value, getdate()) > 7
  ORDER BY q.value DESC
""", timeout = 300)

        rows = cursor.fetchall()
        cursor.close()
        if not len(rows):
            raise NothingFoundError('Exiting.')
    except cdrdb.Error, info:
        l.write("Failure retrieving Licensee Info\n%s" % 
                 info[1][0], stdout = True)
        sendErrorMessage('SQL query timeout error: Query 1')
        raise

    # Create the message body and display the query results
    # -----------------------------------------------------
    mailBody = """\
<html>
 <head>
  <title>New Test Licensees to Contact</title>
  <style type='text/css'>
   table td { border-collapse: collapse; } 
   th       { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>New Test Licensees to Contact</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Licensee</th>
    <th>Activation Date</th>
    <th>Days since</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

    # Display the records of protocols with NCT ID
    # --------------------------------------------
    for (cdrId, licensee, testDate, days) in rows:
        mailBody += """\
   <tr>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (cdrId, licensee, testDate, days)

    mailBody += """\
  </table>

 </body>
</html>
"""

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    SMTP_RELAY   = "MAILFWD.NIH.GOV"
    strFrom      = "PDQ Operator <operator@cips.nci.nih.gov>"
    strTo        = ["VE Test <***REMOVED***>"]

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (strFrom, ", ".join(strTo), cdr.PUB_NAME.capitalize(),
       'Licensees to be contacted')

    mailHeader   += "Content-type: text/html; charset=iso-8859-1\n"

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    #print message

    # Sending out the email 
    # ---------------------
    server = smtplib.SMTP(SMTP_RELAY)
    if emailMode:
        server.sendmail(strFrom, strTo, message)
    else:
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)
    server.quit()

except NothingFoundError, arg:
    msg  = "No new test licensee to be notified"
    l.write("%s" % msg, stdout = True)
    l.write("%s" % arg, stdout = True)
except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("NotifyTestLicensee - Finished", stdout = True)
sys.exit(0)
