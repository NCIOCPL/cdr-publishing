#
# This script starts the publishing service.
#
# $Id: PublishingService.py,v 1.6 2002-08-02 03:45:29 ameyer Exp $
# $Log: not supported by cvs2svn $
# Revision 1.5  2002/02/20 22:25:10  Pzhang
# First version of GOOD publish.py.
#
# Revision 1.4  2002/02/20 15:10:14  pzhang
# Modified SCRIPT to point to /cdr/lib/python/publish.py. Avoided duplicate
# files in /cdr/publishing/publish.py this way.
#
# Revision 1.3  2002/02/19 23:13:33  ameyer
# Removed SCRIPT and replaced it with BASEDIR in keeping with new decisions
# about where things are.
#
# Revision 1.2  2002/02/06 16:22:39  pzhang
# Added Log. Don't want to change SCRIPT here; change cdr.py.
#
#

import cdrdb, cdrbatch, os, time, cdr, sys, string

# Sleep time between checks for things to do
sleepSecs = len(sys.argv) > 1 and string.atoi(sys.argv[1]) or 10

# Script and log file for publishing
PUBSCRIPT = cdr.BASEDIR + "/publishing/publish.py"
PUBLOG    = cdr.DEFAULT_LOGDIR + "/publish.log"

# Publishing queries
query  = """\
SELECT id
  FROM pub_proc
 WHERE status = 'Ready'
"""
update = """\
UPDATE pub_proc
   SET status = 'Started'
 WHERE status = 'Ready'
"""

# Query for batch job initiation
batchQry = "SELECT id, command FROM batch_job WHERE status='%s'" %\
           cdrbatch.ST_QUEUED

# Logfile for publishing
PUBLOG = cdr.DEFAULT_LOGDIR + "/publish.log"

conn = None
while 1:
    try:
        # Connection for all efforts
        if not conn:
            conn = cdrdb.connect("CdrPublishing")
        cursor = conn.cursor()

        # Publishing
        cursor.execute(query)
        rows = cursor.fetchall()
        if len(rows):
            cursor.execute(update)
        conn.commit()
        cursor.close()
        cursor = None
        for row in rows:
            #print "publishing job %d" % row[0]
            os.spawnv(os.P_NOWAIT, cdr.PYTHON, ("CdrPublish", PUBSCRIPT,
                                                str(row[0])))

        # Batch jobs
        try:
            cursor = conn.cursor()
            cursor.execute(batchQry)
            rows = cursor.fetchall()

            if len (rows):
                # Process each queued job
                for jobId, cmd in rows:
                    # Is the command cdr relative or absolute?
                    if not os.path.isabs (cmd):
                        cmd = cdr.BASEDIR + '/' + cmd

                    # By convention, all jobs take a job id as last parameter
                    script = "%s %d" % (cmd, jobId)

                    # Distinguish scripts requiring an interpreter from others
                    # Python script
                    if cmd.endswith ('.py'):
                        cmd = cdr.PYTHON

                    # Perl script (may never be used)
                    elif cmd.endswith ('.pl'):
                        cmd = cdr.PERL

                    # Executable or .bat/.cmd file
                    else:
                        cmd = script
                        script = ""

                    # Indicate that we are initiating job
                    cdr.logwrite ("Daemon: about to show initiation of %s" %\
                                  script, cdrbatch.LF)
                    cdrbatch.sendSignal (conn, jobId, cdrbatch.ST_INITIATING,
                                         cdrbatch.PROC_DAEMON)
                    cdr.logwrite ("Daemon: back from initiation", cdrbatch.LF)

                    # Done with cursor
                    conn.commit()
                    cursor.close()

                    # Spawn the job
                    # Haven't found a good way to find out if it worked
                    # Return code doesn't help much
                    # Called job should update status to cdrbatch.ST_INPROCESS
                    cdr.logwrite ("Daemon: about to spawn: %s %s" % \
                                  (cmd, script), cdrbatch.LF)
                    os.spawnv (os.P_NOWAIT, cmd, (cmd, script))

                    # Record it
                    cdr.logwrite ("Daemon: spawned: %s %s" % (cmd, script),
                                  cdrbatch.LF)
        # Log any errors
        except cdrbatch.BatchException, be:
            cdr.logwrite ("Daemon - batch execution error: %s", str(be),
                          cdrbatch.LF)
        except cdrdb.Error, info:
            cdr.logwrite ("Daemon - batch database error: %s" % info[1][0],
                          cdrbatch.LF)
            conn = None

    except cdrdb.Error, info:
        # Log publishing job initiation errors
        cdr.logwrite ('Database failure: %s' % info[1][0], PUBLOG)
        conn = None

    # Do it all again after a decent interval
    time.sleep(sleepSecs)
