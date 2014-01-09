#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to check if a published (pushed to Cancer.gov) protocol has
# the flag CTGovDuplicate.
# These documents indicate that the NCI is now taking over a document
# previously handled by the NLM (ClinicalTrials.gov).
# Send out a notification about this document.
# ---------------------------------------------------------------------
# $Author$
# Created:          2009-01-07        Volker Englisch
# Last Modified:    $$
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/CheckCTGovDuplicate.py,v $
# $Revision$
#
# $Id$
# $Log: not supported by cvs2svn $
# Revision 1.3  2009/03/23 17:47:40  venglisc
# Needed to increase the default time for the SQL query to run. (Bug 4429)
#
# Revision 1.2  2009/03/23 17:23:52  venglisc
# Modifying email list to come from the CDR. (Bug 4429)
#
# Revision 1.1  2009/02/26 21:43:43  venglisc
# Initial version of program to check the CDR if any new protocols with the
# element CTGovDuplicate have been published. (Bug 4429)
#
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob

OUTPUTBASE     = cdr.BASEDIR + "/Output/CTGovDuplicate"
DOC_FILE       = "CTGovDuplicate"
LOGNAME        = "CTGovDuplicate.log"

now            = time.localtime()
outputFile     = '%s_%s.txt' % (DOC_FILE, time.strftime("%Y%m%d%H%M%S", now))

testMode       = None
emailMode      = None

# Create an exception allowing us to break out if there are no new
# protocols found to report.
# ----------------------------------------------------------------
class NoNewDocumentsError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
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
    parser.add_option('-f', '--filename',
                      action = 'store', dest = 'file',
                      help = 'run diff on this file')

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

    if parser.values.file:
        file = parser.values.file
        l.write("Comparing output to file: %s" % file, stdout = True)

    return parser


# ---------------------------------------------------------------------
# Selecting the protocol list created last time this program ran
# ---------------------------------------------------------------------
def getLastProtocolList(directory = cdr.BASEDIR + '/Output/CTGovDuplicate'):
    os.chdir(directory)
    if testMode:
        searchFor = '*.test.txt'
    else:
        searchFor = 'CTGovDuplicate_??????????????.txt'

    fileList = glob.glob(searchFor)
    if not fileList: return
    fileList.sort()
    fileList.reverse()
    return (fileList[0])
    
# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CTGovDuplicate - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
if options.values.file:
    useFile = options.values.file
    oldFile = getLastProtocolList(OUTPUTBASE)
    l.write("  Last protocol list was: %s" % oldFile, stdout = True)
else:
    useFile = getLastProtocolList(OUTPUTBASE)
    l.write("Comparing output to file: %s" % useFile, stdout = True)

if testMode:
    outputFile = outputFile.replace('.txt', '.test.txt')

path = OUTPUTBASE + '/%s'
l.write("    New protocol list is: %s" % outputFile, stdout = True)
 
try:
    # Open the latest manifest file (or the one specified) and read 
    # the content
    # -------------------------------------------------------------
    protocols = {}
    oldFile = []
    oldIds = []
    # A) If the file name has been passed as a parameter and the file 
    #    doesn't exist, exit.
    # B) If no file exists in the directory this is the first time the 
    #    process is run and we continue
    # --------------------------------------------------------------------
    if options.values.file and not os.access(path % useFile, os.F_OK):
        sys.exit('Invalid File Name: %s' % useFile)
    elif not options.values.file and not os.access(path % useFile, os.F_OK):
        l.write("No files found.  Assuming new directory", stdout = True)
    else:
        f = open(path % useFile, 'r')
        protocols = f.readlines()
        f.close()

        # Read the list of previously published protocols
        # ------------------------------------------------
        for row in protocols:
            oldIds.append(int(row.split('\t')[0]))


    # Connect to the database to get the full list of protocols with
    # the CTGovDuplicate element.
    # --------------------------------------------------------------
    newWithdrawn = []

    conn = cdrdb.connect()
    cursor = conn.cursor()
        
    cursor.execute("""\
        SELECT cg.id as "CDR-ID", pid.value as "Primary ID", 
               nid.value as "NCT-ID", o.value as "Lead Org Name",
               v.comment
               --,cg.pub_proc, p.value, pp.started, pp.completed, pp.status
          FROM pub_proc_cg cg
          JOIN query_term_pub p
            ON cg.id = p.doc_id
          JOIN pub_proc pp
            ON pp.id = cg.pub_proc
        -- Get Primary ID
          JOIN query_term_pub pid
            ON p.doc_id = pid.doc_id
           AND pid.path = '/InScopeProtocol/ProtocolIDs/PrimaryID/IDString'
        -- Get Other-ID
          JOIN query_term_pub nid
            ON p.doc_id = nid.doc_id
           AND nid.path = '/InScopeProtocol/ProtocolIDs/OtherID/IDString'
          JOIN query_term_pub nt
            ON p.doc_id = nt.doc_id
           AND nt.path = '/InScopeProtocol/ProtocolIDs/OtherID/IDType'
           AND nt.value = 'ClinicalTrials.gov ID'
           AND LEFT(nt.node_loc, 8) = LEFT(nid.node_loc, 8)
        -- Get Lead Org ID
          JOIN query_term_pub oid
            ON p.doc_id = oid.doc_id
           AND oid.path = '/InScopeProtocol/ProtocolAdminInfo' + 
                          '/ProtocolLeadOrg/LeadOrganizationID/@cdr:ref'
        -- Get Lead Org Name
          JOIN query_term_pub o
            ON oid.int_val = o.doc_id
           AND o.path = '/Organization/OrganizationNameInformation' + 
                        '/OfficialName/Name'
        -- Get the Version comment
          JOIN doc_version v
            ON v.id = p.doc_id
           AND v.publishable = 'Y'
           AND v.num = (SELECT MAX(num) 
                          FROM doc_version i 
                         WHERE i.id = v.id)
         WHERE p.path = '/InScopeProtocol/CTGovDuplicate'
        --   AND pp.id = (SELECT MAX(id) 
        --                  FROM pub_proc 
        --                 WHERE status in ('Success', 'Verifying') 
        --                   AND pub_subset like 'Push_%%')
           ORDER by cg.id""", timeout=300)

    rows = cursor.fetchall()
    cursor.close()

    # Create the new manifest file and identify those records that
    # are new since the last time this job ran (by comparing to the
    # file created last time).
    # -------------------------------------------------------------
    f = open(path % outputFile, 'w')
    newIds = []
    l.write("", stdout = True)
    l.write("List of CTGovDuplicate protocols", stdout = False)
    l.write("--------------------------------",   stdout = False)
    for (cdrId, protocolId, nctId, orgName, comment) in rows:
        l.write("%s, %s, %s, %s" % (cdrId, protocolId, nctId, orgName), 
                                    stdout = False)

        if cdrId not in oldIds:
            f.write("%10s\t%25s\t%12s\tNew\n" % (cdrId, protocolId, nctId))
            newIds.append(cdrId)
        else:
            f.write("%10s\t%25s\t%12s\n" % (cdrId, protocolId, nctId))
    f.close()

    # Create the message body and display the query results
    # -----------------------------------------------------
    if newIds:
        l.write("", stdout = True)
        l.write('List of new CTGovDuplicate protocols', stdout = True)
        l.write('%s' % newIds, stdout = True)
        mailBody = """\
<html>
 <head>
  <title>Transfer Ownership to NCI</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>Transfer Ownership to NCI</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Primary ID</th>
    <th>NCT-ID</th>
    <th>Lead Org Name</th>
    <th>Comments</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

        for (cdrId, protocolId, nctId, orgName, comment) in rows:
            if cdrId in newIds:
                mailBody += """\
   <tr>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>
     <a href="http://www.clinicaltrials.gov/ct2/show/%s">%s</a>
    </td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (cdrId, protocolId, nctId, nctId, orgName, comment)

        mailBody += """\
  </table>

 </body>
</html>
"""
    else:
        raise NoNewDocumentsError('NoNewDocumentsError')
        

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    SMTP_RELAY   = "MAILFWD.NIH.GOV"
    strFrom      = "PDQ Operator <NCIPDQoperator@mail.nih.gov>"
    if testMode:
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        strTo    = cdr.getEmailList('CTGov Duplicate Notification')
        strTo.append(u'Cherryl Villanueva <***REMOVED***>')
        strTo.append(u'Alexandra Valentine <***REMOVED***>')

    if cdr.h.org == 'OCE':
        subject   = "%s: %s" % (cdr.PUB_NAME.capitalize(),
                    'Transfer Ownership to NCI')
    else:
        subject   = "%s-%s: %s" %(cdr.h.org, cdr.h.tier,
                    'Transfer Ownership to NCI')
    
    mailHeader   = """\
From: %s
To: %s
%s
""" % (strFrom, ", ".join(strTo), subject)

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
    msg  = "No documents found with 'CTGovDuplicate' element"
    l.write("   %s" % msg, stdout = True)
    l.write("   %s" % arg, stdout = True)
except NoNewDocumentsError, arg:
    msg  = "No new documents found with 'CTGovDuplicate' element"
    l.write("", stdout = True)
    l.write("   %s" % msg, stdout = True)
    l.write("   %s" % arg, stdout = True)
except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("CTGovDuplicate - Finished", stdout = True)
sys.exit(0)
