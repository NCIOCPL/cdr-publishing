#----------------------------------------------------------------------
#
# $Id$
#
# Script intended to submit an email to the Visuals OnLine (VOL) 
# manager (Kevin Broun) when a media document has been updated or 
# added to Cancer.gov.
#
# $Log: not supported by cvs2svn $
# Revision 1.1  2009/01/23 15:59:41  venglisc
# Initial copy of program to notify the visual online person about newly
# published media documents. (Bug 4402)
#
#----------------------------------------------------------------------
import os, sys, cdr, time, optparse, cdrdb

FILEBASE           = "Notify_VOL"
LOGNAME            = "%s.log" % FILEBASE
jobTime            = time.localtime(time.time())
today              = time.strftime("%Y-%m-%d", jobTime)

testMode   = None
fullUpdate = None
pubDir     = None


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
    parser.add_option('-s', '--startdate', dest = 'startDate', 
                      metavar = 'STARTDATE',
                      help = 'start date of time frame (default one week)')
    parser.add_option('-e', '--enddate', dest = 'endDate', 
                      metavar = 'ENDDATE',
                      help = 'end date of time frame (default today)')

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

    if parser.values.startDate:
        startDate = parser.values.startDate
        l.write("Start Date: %s" % startDate, stdout = True)

    if parser.values.endDate:
        endDate = parser.values.endDate
        l.write("End   Date: %s" % endDate, stdout = True)

    return parser


# ------------------------------------------------------------
# Function to check the database if media documents where 
# updated for the given time frame.
# ------------------------------------------------------------
def checkMediaUpdates(sDate, eDate):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        cursor.execute("""\
           SELECT d.id
             FROM pub_proc_doc ppd
             JOIN pub_proc pp
               ON pp.id = ppd.pub_proc
             JOIN document d
               ON d.id = ppd.doc_id
             JOIN doc_type dt
               ON dt.id = d.doc_type
              AND dt.name = 'Media'
            WHERE pub_subset like 'Push_%%'
              AND status in ('Success', 'Verifying')
              AND pp.started between '%s' AND '%s'
              AND val_status = 'V'
              AND active_status = 'A'
              AND NOT exists (
                   SELECT 'x'
                     FROM query_term_pub i
                    WHERE i.doc_id = d.id
                      AND path = '/Media/PhysicalMedia/SoundData/SoundEncoding'
                   )
            ORDER BY d.id
        """ % (sDate, eDate), timeout=300)
        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure finding updated media documents: %s" % (info[1][0]))

    if rows:
        return True
    return False

# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------
# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGNAME)
l.write('Notify_VOL - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If only the start or end date are specified, the timeframe will
# be set to one week.  Otherwise it's whatever dates are passed
# or one week prior to today if no dates are specified.
# ---------------------------------------------------------------
endDate   = options.values.endDate   or today
startDate = options.values.startDate \
            or cdr.calculateDateByOffset(-6, referenceDate = endDate)

# Checking if Media documents were updated for the given
# time frame.
# ----------------------------------------------------------
mediaChanges = checkMediaUpdates(startDate, endDate)

# Print the result
# ----------------
l.write('Time Frame:  %s to %s' % (startDate, endDate), stdout = True)
l.write('Media Documents Updated: %s' % mediaChanges, stdout = True)

# Setting up email message to be send to users
# --------------------------------------------
# machine  = socket.gethostname().split('.')[0]
sender   = '***REMOVED***'
subject = cdr.emailSubject('List of Updated Media Documents')

body     = """
<html>
 <head>
  <title>Media List Report</title>
 </head>
 <body>
  <h3>Updated CDR Media Documents</h3>
   Click the link to view the latest 
   <a href="%s/cgi-bin/cdr/""" % cdr.CBIIT_NAMES[2]
body   += """PubStatsByDate.py?session=cdrguest&VOL=Y&doctype=Media&"""
body   += """datefrom=%s&dateto=%s">""" % (startDate, endDate)
body   += """Media Change Report</a> """
body   += """for documents published <br/>between %s and %s.
  <br/><br/>
  For questions or comments please contact
    <a href="mailto:***REMOVED***">Volker Englisch</a>.
 </body>
</html>
""" % (startDate, endDate)

# Don't send emails to everyone if we're testing 
# ----------------------------------------------
emailDL = cdr.getEmailList('VOL Notification')
emailDL.sort()
if not len(emailDL) or testMode:
    recips = ["***REMOVED***"]
else:
    recips = emailDL

if mediaChanges and recips:
    l.write("Email submitted to DL", stdout = True)
    cdr.sendMail(sender, recips, subject, body, html = 1)
else:
    # Else statement included to monitor the program
    recips = ["***REMOVED***"]
    l.write("Email NOT submitted to DL", stdout = True)
    cdr.sendMail(sender, recips, subject, body, html = 1)

# All done, going home now
# ------------------------
cpu = time.clock()
l.write('CPU time: %6.2f seconds' % cpu, stdout = True)
l.write('Notify_VOL - Finished', stdout = True)
sys.exit(0)
