#################################################################
# Modify the pub_proc_cg table to support testing of nightly publishing
#
# $Id: TestModifyPubProcCG.py,v 1.2 2007-05-11 03:50:54 ameyer Exp $
#
# $Log: not supported by cvs2svn $
# Revision 1.1  2007/04/19 23:05:22  ameyer
# Initial version.
#
#################################################################

import sys, cdr, cdrdb

CHG_STATE = '=ChangeDocs'
NEW_STATE = '=PubAsNewDocs'
VER_STATE = '=NewVersionDocs'
DEL_STATE = '=InactivateDocs'
ACT_STATE = '=ReactivateDocs'

validStates = set((CHG_STATE, NEW_STATE, VER_STATE, DEL_STATE, ACT_STATE))

chg_count = 0
new_count = 0
ver_count = 0
del_count = 0
act_count = 0
lineNum   = 0
err_count = 0

def changeDoc(docId):
    """
    Modify the text of the xml column in pub_proc_cg.

    Does it the same for any doc type, prepending "TEST " to an
    element content.
    """
    global cursor

    # Get what's there
    cursor.execute("SELECT xml FROM pub_proc_cg WHERE id=%d" % docId)
    text = cursor.fetchone()[0]

    # Find the fourth tag, doesn't matter what it is
    # Probably don't need to do this, but it seems a bit safer than
    #  malforming the doc
    pos = 0
    for i in range(4):
        pos = text.find('>', pos + 1)

    # Insert a literal
    pos += 1
    xml = text[:pos] + "TEST " + text[pos:]

    # Put it back in the database
    cursor.execute("UPDATE pub_proc_cg SET xml=? WHERE id=?", (xml, docId))


def pubAsNewDoc(docId):
    """
    Make it appear that this doc was not published, or had been removed,
    by deleting it from pub_proc_cg.
    """
    global cursor

    # Get what's there
    cursor.execute("DELETE pub_proc_cg WHERE id=%d" % docId)


def newVersionDoc(docId, pubVerNum):
    """
    Make whatever version is in the doc_version table appear to be a
    new version by modifying the text of the pub_proc_cg.xml, and resaving the
    last publishable version as a new publishable version.
    """
    # Get and re-store the doc as a new publishable version
    doc = cdr.getDoc(session, docId, checkout='Y', version=pubVerNum, xml='Y')
    (repId, errors) = cdr.repDoc(session, doc=doc,
            comment='New version created by MFP test program for testing',
            checkIn='Y', val='Y', ver='Y', verPublishable='Y',
            showWarnings=True)

    if errors:
        error("Error getting/replacing docId=%d: %s" % (docId, errors))

    # Update pub_proc_cg.xml so this version will appear different
    changeDoc(docId)


def inactivateDoc(docId):
    """
    Cause the document to be removed by changing its active_status
    in the document table to 'I'.

    Does nothing if doc is already marked inactive.
    """
    global cursor

    cursor.execute("UPDATE document SET active_status='I' where id=%d" % \
                   docId)

def reactivateDoc(docId):
    """
    Cause the document to be restored by changing its active_status
    in the document table to 'A'.

    The doc will be published as new if it had previously been removed
    by a publishing job.  Otherwise nothing will happen.

    Does nothing if doc is already marked active.
    """
    global cursor

    cursor.execute("UPDATE document SET active_status='A' where id=%d" % \
                   docId)


def error(msg):
    """
    Display error message on the console.

    In test mode, continue, in run mode, halt.
    """
    global mode, lineNum, err_count

    sys.stderr.write("line %d: %s\n" % (lineNum, msg))
    err_count += 1
    if mode == 'run':
        sys.stderr.write("Error in run mode causes abort")
        sys.exit(1)

# Main
if len(sys.argv) != 5:
    sys.stderr.write(\
        "usage: TestModifyPubProcCG.py userId pw docIdFileName 'test'|'run'\n")
    sys.stderr.write("  ALWAYS use test mode first\n")
    sys.exit(1)

# Open doc id file, blow up if failed
inf = open(sys.argv[3], "r")

# Require user to explicitly test or run
mode = sys.argv[4]
if mode != 'test' and mode != 'run':
    sys.stderr.write("Specify 'test' or 'run'")
    sys.exit(1)

# DEBUG
# mode = 'test'

# Connect to CDR and database or blow up
session = cdr.login(sys.argv[1], sys.argv[2])
if session.startswith("Error"):
    sys.stderr.write("Logging in: %s" % session)
    sys.exit(1)
conn = cdrdb.connect("CdrPublishing")
cursor = conn.cursor()

# What we're doing with doc IDs
state = None

while True:
    docId = None
    line = inf.readline()
    lineNum += 1
    if not line:
        break

    # Normalize
    line = line.strip()

    # Blanks and comments
    if not line or line[0] == '#':
        continue

    # Block comments - no nesting allowed
    # Comment delimiters must be alone on a line
    if line == "/*":
        if state == "comment":
            error("Nested comments not allowed")
        else:
            saveState = state
            state = "comment"
        continue
    elif line == "*/":
        if state != "comment":
            error("Close comment */ with no open comment /*")
        else:
            state = saveState
        continue
    if state == "comment":
        continue

    # Is it a doc ID?
    docId = None
    try:
        docId = int(line)
    except ValueError:
        pass

    # Is it a keyword
    if not docId:
        if line not in validStates:
            error("%s is not a keyword or a numeric doc id" % line)
        else:
            state = line

    else:
        # We've got a docId, is it legal here?
        if not state:
            error("DocID %d appeared before any state is declared" % docId)

        # Is docId in pub_proc_cg?
        # Don't do this check if reactivating a doc
        if state != ACT_STATE:
            cursor.execute("SELECT 0 FROM pub_proc_cg WHERE id=%d" % docId)
            if not cursor.fetchone():
                error("No instance of docId=%d found in pub_proc_cg" % docId)

        # Is there a publishable version to use?
        docIdStr = cdr.normalize(docId)
        pubVerNum = cdr.lastVersions(session, docIdStr)[1]
        if pubVerNum == -1:
            error("No publishable version of docId=%d found, can't happen" \
                  % docId)

        # If we're really doing it, process the docId
        if mode == 'run':
            if state == CHG_STATE:
                changeDoc(docId)
                chg_count += 1
            elif state == NEW_STATE:
                pubAsNewDoc(docId)
                new_count += 1
            elif state == VER_STATE:
                newVersionDoc(docId, pubVerNum)
                ver_count += 1
            elif state == DEL_STATE:
                inactivateDoc(docId)
                del_count += 1
            elif state == ACT_STATE:
                reactivateDoc(docId)
                act_count += 1

conn.commit()

# Report
if mode == 'test':
    print("%d errors" % err_count)
else:
    print ("%6d changed docs" % chg_count)
    print ("%6d newly published docs" % new_count)
    print ("%6d new doc versions" % ver_count)
    print ("%6d inactivated docs" % del_count)
    print ("%6d reactivated docs" % act_count)
