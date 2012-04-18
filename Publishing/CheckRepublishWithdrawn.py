#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to check if a protocol has been published for the first time
# after it had previously been removed/withdrawn.
# These documents need to be reported to the NLM so that they can 
# change the protocols 'Withdrawn' status and accept updates from PDQ.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2009-01-28        Volker Englisch
# Last Modified:    $Date: 2009-06-04 21:44:10 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/CheckRepublishWithdrawn.py,v $
# $Revision: 1.3 $
#
# $Id: CheckRepublishWithdrawn.py,v 1.3 2009-06-04 21:44:10 venglisc Exp $
# $Log: not supported by cvs2svn $
# Revision 1.2  2009/02/27 23:23:02  venglisc
# Added comment and reset the test email DL. (Bug 4450)
#
# Revision 1.1  2009/02/26 22:05:55  venglisc
# Initial copy of program to identify protocols previously withdrawn and now
# published again.
#
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib

OUTPUTBASE     = cdr.BASEDIR + "/Output/NLMExport"
WITHDRAWN_LIST = "WithdrawnFromPDQ.txt"
LOGNAME        = "CheckRepublishWithdrawn.log"

now            = time.localtime(time.time())

testMode       = None
emailMode      = None

# Create an exception allowing us to break out if there are no new
# protocols found to report.
# ----------------------------------------------------------------
class NothingFoundError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArguments(args):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    usage = "usage: %prog [--livemode | --testmode] [options]"
    parser = optparse.OptionParser(usage = usage)

    parser.set_defaults(testMode = True)
    parser.set_defaults(emailMode = True)
    parser.add_option('-t', '--testmode',
                      action = 'store_true', dest = 'testMode',
                      help = 'running in TEST mode')
    parser.add_option('-l', '--livemode',
                      action = 'store_false', dest = 'testMode',
                      help = 'running in LIVE mode')
    parser.add_option('-e', '--email',
                      action = 'store_true', dest = 'emailMode',
                      help = 'running in EMAIL mode')
    parser.add_option('-n', '--noemail',
                      action = 'store_false', dest = 'emailMode',
                      help = 'running in NOEMAIL mode')

    # Exit if no command line argument has been specified
    # ---------------------------------------------------
    if len(args[1:]) == 0:
        parser.print_help()
        sys.exit('No arguments given!')

    (options, args) = parser.parse_args()

    # Read and process options, if any
    # --------------------------------
    if parser.values.testMode:
        l.write("Running in TEST mode", stdout = True)
    else:
        l.write("Running in LIVE mode", stdout = True)

    if parser.values.emailMode:
        l.write("Running in EMAIL mode", stdout = True)
    else:
        l.write("Running in NOEMAIL mode", stdout = True)

    return parser


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CheckRepublishWithdrawn - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode
 
try:
    # Connect to the database to get the reason for withdrawl
    # -------------------------------------------------------
    conn = cdrdb.connect()
    cursor = conn.cursor()
        

    # Query to find all documents that have been published
    # again after they had been removed from Cancer.gov.
    # -----------------------------------------------------
    cursor.execute("""\
SELECT ppd.pub_proc, ppd.doc_id, pp.completed, ppd.doc_version, ppd.removed,
       p.pub_proc, p.doc_id, p.doc_version, p.removed
  FROM pub_proc_doc ppd                 -- publishing job/version which removed
  JOIN pub_proc_doc p                   -- document latest version published
    ON ppd.doc_id = p.doc_id
   -- AND p.doc_version = (select MAX(doc_version) 
   --                        FROM pub_proc_doc i 
   --                       WHERE i.doc_id = p.doc_id)
   AND p.pub_proc    = (select MAX(pub_proc) 
                          FROM pub_proc_doc i 
                         WHERE i.doc_id = p.doc_id)
  JOIN document d                       -- limit output to InScopeProtocols
    ON d.id = p.doc_id
   AND doc_type = 18
  JOIN pub_proc pp                      -- limit output to successfull pub
    ON pp.id = ppd.pub_proc             -- jobs of the remove job
   AND pp.status = 'Success'
   AND pp.pub_subset like 'Push_%%'
   AND pp.id = (SELECT MAX(pub_proc)    -- in case a document has been
                  FROM pub_proc_doc i   -- removed multiple times only
                 WHERE i.removed = 'Y'  -- pick up the latest event
                   AND i.doc_id = ppd.doc_id)

  JOIN pub_proc pp2                     -- limit output to successfull pub
    ON pp2.id = p.pub_proc              -- jobs of the latest job
   AND (pp2.status = 'Success'
        OR
        pp2.status = 'Verifying')
 WHERE ppd.removed = 'Y' 
   AND p.removed = 'N'
   AND ppd.pub_proc < p.pub_proc
   AND d.active_status = 'A'
 ORDER BY ppd.doc_id
""", timeout=300)

    rows = cursor.fetchall()
    cursor.close()

    # Find out the latest publishing jobId (latest push job)
    # Note: If for some reason a publishing job ran but this publishing
    #       job did not create any document to be pushed to Cancer.gov
    #       a previously reported would be reported again due to the 
    #       join to the pub_proc_doc table even though a new publishing
    #       event happend (but no push event).
    # -----------------------------------------------------------------
    cursor.execute("""\
SELECT MAX(pub_proc)
  FROM pub_proc_doc ppd
  JOIN pub_proc pp
    ON pp.id = ppd.pub_proc
   AND pub_subset like 'Push_%%'
   AND (status = 'Success'
        OR 
        status = 'Verifying')
""")

    lastJobId = cursor.fetchone()

    # Now find out if this latest publishing job is the first publishing 
    # job for this document since the last publishing event removing it.
    # There could have been many other publishing events for this document
    # already.  If this is the first publishing event since the last 
    # removal *and* it is the same publishing event as the latest one we
    # found a document to report on. 
    # ---------------------------------------------------------------------
    allCdrIds  = []
    removalDate = {}
    for row in rows:
        cdrId = row[1]
        rmJobId = row[0]
        cursor.execute("""\
SELECT MIN(pub_proc)
  FROM pub_proc_doc ppd
  JOIN pub_proc pp
    ON pp.id = ppd.pub_proc
   AND pub_subset like 'Push_%%'
   AND (status = 'Success'
        OR
        status = 'Verifying')
 WHERE doc_id = %s 
   AND pub_proc > (SELECT MAX(pub_proc) 
                      FROM pub_proc_doc i 
                     WHERE removed = 'Y' 
                       AND i.doc_id = ppd.doc_id)
""" % cdrId)

        lastJobIdForDoc = cursor.fetchone()
        
        if lastJobIdForDoc == lastJobId:
            allCdrIds.append(cdrId)
            removalDate[cdrId] = row[2][:10]
            print "LastJobId = %s" % lastJobIdForDoc[0]
            l.write("rm/repub:Job-ID, CDR-ID, rm-date, Version, rm-flag", 
                     stdout = True)
            l.write("%s" % row, stdout = True)

    # Find the information to be displayed on the report for all of the 
    # protocols identified as those published after previously being 
    # removed.
    # ------------------------------------------------------------------
    if not allCdrIds:
        raise NothingFoundError('Exiting.')

    cursor.execute("""\
          SELECT q.doc_id, q.value, n.value, s.value, oname.value, 
                 d.comment --, o.value
            FROM query_term_pub q
 LEFT OUTER JOIN query_term_pub c
              ON q.doc_id   = c.doc_id
             AND c.path     = '/InScopeProtocol/ProtocolIDs/OtherID/IDType'
             AND c.value    = 'ClinicalTrials.gov ID'
 LEFT OUTER JOIN query_term_pub n
              ON c.doc_id   = n.doc_id
             AND n.path     = '/InScopeProtocol/ProtocolIDs/OtherID/IDString'
             AND left(c.node_loc, 8) = left(n.node_loc, 8)
            JOIN query_term_pub s
              ON s.doc_id   = q.doc_id
             AND s.path     = '/InScopeProtocol/ProtocolAdminInfo/' +
                              'CurrentProtocolStatus'
            JOIN query_term_pub o
              ON o.doc_id   = q.doc_id
             AND o.path     = '/InScopeProtocol/ProtocolAdminInfo' +
                             '/ProtocolLeadOrg/LeadOrganizationID/@cdr:ref'
            JOIN query_term_pub oname
              ON o.int_val  = oname.doc_id
             AND oname.path = '/Organization/OrganizationNameInformation' +
                              '/OfficialName/Name'
            JOIN document d
              on q.doc_id = d.id
           WHERE q.doc_id in (%s)
             AND q.path     = '/InScopeProtocol/ProtocolIDs/PrimaryID/IDString'
""" % ','.join(['%s' % x for x in allCdrIds]))

    allRows = cursor.fetchall()

    # Create the message body and display the query results
    # -----------------------------------------------------
    mailBody = """\
<html>
 <head>
  <title>Protocols with status: Withdrawn from PDQ</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>Published trial(s) (previously removed from PDQ and CT.gov)</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Primary ID</th>
    <th>NCT-ID</th>
    <th>Status</th>
    <th>Lead Org</th>
    <th>Removal Date</th>
    <th>Comment</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

    for (cdrId, protId, nctid, status, org, comment) in allRows:
        mailBody += """\
   <tr>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>
     <a href="http://www.clinicaltrials.gov/ct2/show/%s">%s</a>
    </td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (cdrId, protId, nctid or '', nctid or '', status, org, 
       removalDate[cdrId], comment)

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
    if testMode:
        strTo    = ["VE Test <***REMOVED***>"]
                    #"William Osei-Poku <william.osei-poku@lmco.com>", 
                    #"Kimberly Eckley <***REMOVED***>"]
    else:
        strTo    = ["PDQ Operator <operator@cips.nci.nih.gov>", 
                    "William Osei-Poku <***REMOVED***>", 
                    "Diana Bitenas <Diana.bitenas@lmco.com>",
                    "Judy Morris <***REMOVED***>",
                    "Alexandra Valentine <***REMOVED***>",
                    "Cherryl Villanueva <***REMOVED***>"]
                    #"Kimberly Eckley <***REMOVED***>",

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (strFrom, ", ".join(strTo), cdr.PUB_NAME.capitalize(),
       'Published Protocols previously removed from PDQ/CT.gov')

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
        l.write("Email submitted to", stdout = True)
        l.write("%s" % strTo, stdout = True)
    else:
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)
    server.quit()

except NothingFoundError, arg:
    msg  = "No trials published that were previously removed."
    l.write("   %s" % msg, stdout = True)
    l.write("   %s" % arg, stdout = True)
except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("CheckRepublishWithdrawn - Finished", stdout = True)
sys.exit(0)
