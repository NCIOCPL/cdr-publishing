#----------------------------------------------------------------------
#
# $Id$
#
# Script intended to submit an email to the Visuals OnLine (VOL) 
# team when a media document has been updated or added to Cancer.gov.
# New addition - an image that has been made publishable should be
# included as well regardless if it's linked to a document or not.
#
# OCECDR-3752: Modify Media VOL (Visual Online) Report to include all 
#              publishable media (images) docs.
#----------------------------------------------------------------------
import os, sys, cdr, time, optparse, cdrdb

FILEBASE           = "Notify_VOL"
LOGNAME            = "%s.log" % FILEBASE
jobTime            = time.localtime(time.time())
today              = time.strftime("%Y-%m-%d", jobTime)

testMode   = None

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
# Note:  This program used to be run as a two step process.
#        1) Find out if a notification needs to be send
#        2) Create the report with the information requested
#        We could probably create a single query to achieve the
#        same thing what both of these queries are handling
#        but in the interest of time I'm keeping the original
#        approach for now.
# ------------------------------------------------------------
def checkMediaUpdates(sDate, eDate):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """
    # Select all Media (Image) documents with a new publishable version
    # created during the previous week (or the specified time frame)
    # -----------------------------------------------------------------
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        # SELECT d.id, d.val_date, d.title, dv.num, dv.dt, 
        #        dv.val_date, dv.publishable
        cursor.execute("""\
        SELECT d.id
          FROM document d
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'Media'
          JOIN doc_version dv
            ON dv.id = d.id
         WHERE d.val_status = 'V'
           AND d.active_status = 'A'
           AND NOT EXISTS (
                   SELECT 'x'
                     FROM query_term_pub i
                    WHERE i.doc_id = d.id
                      AND path = '/Media/PhysicalMedia/SoundData/SoundEncoding'
                   )
           AND dv.num = (
                   SELECT MAX(num) 
                     FROM doc_version 
                    WHERE id = dv.id
                   )
           AND dv.dt between '%s' AND '%s'
           AND dv.publishable = 'Y'
         ORDER BY d.id
""" % (sDate, eDate), timeout=300)
        ids = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure finding updated media documents: %s" % (info[1][0]))

    if ids:
        # allIds = ', '.join("%s" % x[0] for x in ids)
        # print allIds
        try:
            cursor.execute("""\
         SELECT distinct m.doc_id, m.value, d.first_pub, dv.dt, 
                dv.updated_dt, v.value, dv.num, dv.publishable
           FROM query_term m
LEFT OUTER JOIN query_term v
             ON m.doc_id = v.doc_id
            AND v.path = '/Media/@BlockedFromVOL'
           JOIN doc_version dv
             ON m.doc_id = dv.id
           JOIN document d
             ON dv.id = d.id
           JOIN query_term c
             ON m.doc_id = c.doc_id
          WHERE m.path = '/Media/MediaTitle'
            AND c.path = '/Media/MediaContent/Categories/Category'
            AND c.value not in ('pronunciation', 'meeting recording')
            AND m.doc_id in (%s)
            AND dv.num = (
                          SELECT max(num)
                            FROM doc_version x
                           WHERE x.id = dv.id
                         )
          ORDER BY m.value
""" % ', '.join("%s" % x[0] for x in ids))
            rows = cursor.fetchall()
        except cdrdb.Error, info:
            l.write("Failure finding media data: %s" % (info[1][0]))

        return rows
    return []

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
l.write('Media Documents Updated: \n%s' % mediaChanges, stdout = True)

# Setting up email message to be send to users
# --------------------------------------------
# machine  = socket.gethostname().split('.')[0]
sender   = 'NCIPDQoperator@mail.nih.gov'
subject = cdr.emailSubject('List of Updated Media Documents')

body     = """
<html>
 <head>
  <title>Media List Report</title>
 </head>
  <style type='text/css'>
    body         { background-color: white; }
    H3            { font-weight: bold;
                    font-family: Arial;
                    font-size: 16pt; 
                    margin: 8pt; }
    TABLE.output  { margin-left: auto;
                    margin-right: auto; }
    TABLE.output  TD
                  { padding: 3px; }
    td.header     { font-weight: bold; 
                    text-align: center; }
    tr.odd        { background-color: #E7E7E7; }
    tr.even       { background-color: #FFFFFF; }
    tr.head       { background-color: #D2D2D2; }
    .link         { color: blue; 
                    text-decoration: underline; }
    p             { font-weight: bold;
                    font-family: Arial;
                    font-size: 10pt; }
   </STYLE>

 <body>
  <H3>Updated CDR Media Documents</H3>

     Report includes documents made publishable between
     <b>%s</b> and <b>%s</b><br/>
  <table class="output" border="1">
   <tr class="head">
    <td class="header">CDR-ID</td>
    <td class="header">Media Title</td>
    <td class="header">First Pub Date</td>
    <td class="header">Version Date</td>
    <td class="header">Last Version<br/>Publishable</td>
    <td class="header">Blocked from<br/>VOL</td>
   </tr>
""" % (startDate, endDate)

class_ = "even"
for row in mediaChanges:
    class_ = class_ == "even" and "odd" or "even"
    # print row
    body += """
   <tr class="%s">
    <td class="link">
     <a href="https://cdr.cancer.gov/cgi-bin/cdr/GetCdrImage.py?id=CDR%s.jpg">%s</a>
    </td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td align="center">%s</td>
    <td align="center">%s</td>
   </tr>
       """ % (class_, row[0], row[0], row[1], 
                      row[2] and row[2][:10] or '', 
                      row[3] and row[3][:16] or '', 
                      row[7], 
                      row[5] and 'Y' or '')

body += """
  </table>
 </body>
</html>"""

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
