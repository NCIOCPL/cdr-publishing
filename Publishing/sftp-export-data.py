#!d:/Python/python.exe
"""Copy published data to the public SFTP directory.

Replacement for FtpExportData.py, which created a tar file of the
latest publishing output directory and copied it to an FTP server.
This version installs the PDQ files directly on the storage exposed
by the sFTP server using rsync.
"""

import argparse
import datetime
import glob
import os
import re
import shutil
import sys
import tarfile
import lxml.etree as etree
import cdr
import cdrdb2 as cdrdb

class Control:
    """Master class for executing the processing logic.

    Attributes:
        opts - command-line argument values controlling runtime options
        logger - object for writing to the log file
        job_dir - location of the filtered CDR documents
        week - YYYYWW string representing the ISO week
        types - sequence of exported document types (populated by run() method)
    """

    LICENSEE_DOCS = "d:/cdr/Output/LicenseeDocs"
    PUB_SHADOW = "d:/cdr/sftp_shadow"
    LANGUAGES = { "English": "en", "Spanish": "es" }
    MEDIA_CATALOG = "media_catalog.txt"
    LOGGER = cdr.Logging.get_logger("sftp-export")
    SSH = ("ssh -i d:/etc/cdroperator_rsa "
           "-o LogLevel=error "
           "-o StrictHostKeyChecking=no")
    TIER = cdr.Tier()
    HOST = TIER.hosts["SFTP"]
    USER = "cdroperator"
    PATH = "/sftp/sftphome/cdrstaging/pdq-%s" % TIER.name.lower()

    def __init__(self):
        """Collect the command-line arguments and populate instance attrs.
        """

        parser = argparse.ArgumentParser()
        parser.add_argument("--job", type=int,
                            help="enter job-id to process, default: last")
        parser.add_argument("--level", default="info",
                            help="specify log level, (warn, [info], error)")
        parser.add_argument("--push-only", action="store_true",
                            help="copy the latest existing data set")
        parser.add_argument("--create-only", action="store_true",
                            help="create a new data set but do not copy")
        parser.add_argument("--skip-catalogs", action="store_true",
                            help="skip creating auxilliary files")
        parser.add_argument("--week",
                            help="use at your own risk")
        self.opts = parser.parse_args()
        self.logger = Control.LOGGER
        self.logger.setLevel(self.opts.level.upper())

        # Getting the last job-id that's either passed as an option
        # or defaults to the last job-ID found in the LicenseeDocs directory
        # ------------------------------------------------------------------
        if self.opts.job:
           self.job_id = self.opts.job
        else:
           self.job_id = self.getLastJobId()

        self.job_dir = "%s/Job%d" % (self.LICENSEE_DOCS, self.job_id)
        self.week = self.get_week()
        self.logger.info(47 * "*")
        self.logger.info("sftp-export-data.py - Started")
        self.logger.info(47 * "*")
        self.logger.info("Processing %s", self.job_dir)
        self.logger.info("week %s", self.week)

    def run(self):
        """Top-level processing entry point, performing three tasks:

           1. Create catalog files for what we're publishing
           2. Create compressed archives for the files
           3. Populate the public sFTP data share
        """

        start = datetime.datetime.now()
        os.chdir(self.job_dir)
        self.types = [name for name in os.listdir(".") if os.path.isdir(name)]
        # Creating tar files and auxilliary files
        if not self.opts.push_only:
            if not self.opts.skip_catalogs:
                self.create_catalogs()
            # Create tar files
            self.create_archives()
            # Copy files and move tar files to shadow location
            self.copy_files()

        # Moving tar files and documents (if not suppressed)
        if not self.opts.create_only:
            self.push_files()
            self.fix_permissions()

        elapsed = (datetime.datetime.now() - start).total_seconds()
        self.logger.info("")  # Blank line to format log output
        self.logger.info("completed in %f seconds", elapsed)

        self.logger.info(47 * "*")
        self.logger.info("sftp-export-data.py - Finished")
        self.logger.info(47 * "*")


    def getLastJobId(self):
        """Identify the directory with the latest licensee data

           Since the output of the weekly export job includes a full
           snapshot of the data it only makes sense to update the SFTP
           server with the content of the "last" directory.

           Returns the integer value of the last job-ID in the directory.
        """

        os.chdir(self.LICENSEE_DOCS)
        job_id = 0
        for name in glob.glob("Job*"):
            match = re.match(r"^Job(\d+)$", name)
            if match:
                job_id = max(job_id, int(match.group(1)))
        if not job_id:
            self.logger.info("*** Error: No PDQ partner data found")
            sys.exit(1)
        return job_id

    def create_catalogs(self):
        """Compare what we published last week with what we're publishing now.

        Creates a summary file listing counts for added, removed, and changed
        files of each document type. Also, for each document type for which
        any such differences have occurred since the previous week, creates
        a manifest, listing each document, with the action behind the
        difference.
        """

        for path in glob.glob("%s/*.%s" % (self.job_dir, self.week)):
            self.logger.debug("removing %r", path)
            os.remove(path)
        changes = []
        self.logger.info("Processing doctype directories:")
        for doctype in self.types:
            self.logger.info("...processing %s", doctype)
            olddocs = self.list_docs(self.PUB_SHADOW + "/full", doctype)
            newdocs = self.list_docs(self.job_dir, doctype)
            added = newdocs - olddocs
            dropped = olddocs - newdocs
            kept = olddocs & newdocs
            docs = []
            for name in added:
                docs.append((self.extract_id(name), name, "added"))
            for name in dropped:
                docs.append((self.extract_id(name), name, "dropped"))
            changed = 0
            for name in kept:
                if self.changed(doctype, name):
                    changed += 1
                    docs.append((self.extract_id(name), name, "modified"))
            if docs:
                path = "%s/%s.%s" % (self.job_dir, doctype, self.week)
                with open(path, "w") as fp:
                    for doc_id, name, action in sorted(docs):
                        fp.write("%s:%s\n" % (name, action))
                self.logger.debug("%d line(s) in %s", len(docs), path)
            prefix = "%s.%s" % (doctype, self.week)
            changes.append("%s:added:%d\n" % (prefix, len(added)))
            changes.append("%s:removed:%d\n" % (prefix, len(dropped)))
            changes.append("%s:modified:%d\n" % (prefix, changed))
            if doctype == "Summary":
                self.catalog_summaries(newdocs)
        with open("%s/%s.changes" % (self.job_dir, self.week), "w") as fp:
            for change in sorted(changes):
                fp.write(change)
        self.logger.info("catalogs created")

    def catalog_summaries(self, filenames):
        """Create Summary.en and Summary.es catalog files.

        Each file list the file names (one per line) of each of the summary
        documents in the language of the catalog file.
        """

        summaries = { "en": [], "es": [] }
        for filename in filenames:
            language = self.get_summary_language(filename)
            summaries[language].append((self.extract_id(filename), filename))
        for language in summaries:
            with open("%s/Summary.%s" % (self.job_dir, language), "w") as fp:
                for doc_id, filename in sorted(summaries[language]):
                    fp.write("%s\n" % filename)
        self.logger.info("cataloged summaries by language")

    def get_summary_language(self, filename):
        """Parse the summary document to determine its language.
        """

        path = "%s/Summary/%s" % (self.job_dir, filename)
        root = etree.parse(path).getroot()
        language = cdr.get_text(root.find("SummaryMetaData/SummaryLanguage"))
        return self.LANGUAGES[language]


    def create_archives(self):
        """Create compressed archives for the published files.

        A tar file is created for each of the document types.
        In addition, a complete tar file is created containing
        all of the document types, as well as the catalogs
        created above.
        """
        self.logger.info("")  # Blank line to format log output
        self.logger.info("Creating full.tar.gz")
        os.chdir(self.job_dir)
        with tarfile.open("full.tar.gz", "w:gz") as tar:
            for name in self.types:
                self.logger.info("...adding %s", name)
                tar.add(name)
                catalog_name = "%s.%s" % (name, self.week)
                if os.path.exists(catalog_name):
                    tar.add(catalog_name)
                if name == "Summary":
                    tar.add("Summary.en")
                    tar.add("Summary.es")
            if os.path.exists(self.MEDIA_CATALOG):
                tar.add(self.MEDIA_CATALOG)
            tar.add("%s.changes" % self.week)
        self.logger.info("")
        self.logger.info("Creating doctype tar files:")
        for name in self.types:
            tarname = "%s.tar.gz" % name
            with tarfile.open(tarname, "w:gz") as tar:
                self.logger.info("...creating %s.tar.gz", name)
                tar.add(name)


    def copy_files(self):
        """Populate the local sFTP shadow directory.

        Copy the individual document files and catalogs to the shadow
        directory, and move the compressed archive files to that
        location.
        """

        self.logger.info("")  # Blank line to format log output
        self.logger.info("Copying files to shadow location")
        os.chdir(self.job_dir)
        destination = "%s/full.tar.gz" % self.PUB_SHADOW
        try:
            os.remove(destination)
        except:
            print("Can't remove %s", destination)
            pass
        shutil.move("full.tar.gz", destination)
        full = "%s/full" % self.PUB_SHADOW
        shutil.rmtree(full, ignore_errors=True)
        os.mkdir(full)
        shutil.copy("%s.changes" % self.week, full)
        if os.path.exists(self.MEDIA_CATALOG):
            shutil.copy(self.MEDIA_CATALOG, full)
        for name in self.types:
            destination = "%s/%s" % (full, name)
            self.logger.info("...copying %s", name)
            shutil.copytree(name, destination)
            shutil.move("%s.tar.gz" % name, "%s.tar.gz" % destination)
            catalog_name = "%s.%s" % (name, self.week)
            if os.path.exists(catalog_name):
                shutil.copy(catalog_name, full)
            if name == "Summary":
                shutil.copy("Summary.en", full)
                shutil.copy("Summary.es", full)


    # Using rsync command to update the FTP server content
    # ----------------------------------------------------
    def push_files(self):
        """Update the sFTP server with the content of the shadow directory.

        rsync the individual document files and catalogs from the shadow
        directory to the sFTP server.
        """

        args = self.SSH, self.USER, self.HOST, self.PATH
        command = 'rsync --delete -rae "%s" full* %s@%s:%s' % args
        self.logger.info("")  # Blank line to format log output
        self.logger.info("ssh host: %s", self.HOST)
        self.logger.debug("ssh user: %s", self.USER)
        self.logger.info("rsync command: %s", command)

        os.chdir(self.PUB_SHADOW)

        result = cdr.runCommand(command)
        self.logger.info("")  # Blank line to format log output
        self.logger.info("*** runCommand output")
        self.logger.info(result.output)

        if result.error:
            self.logger.info("*** Error:")
            self.logger.info(result.error)
            self.logger.info("finished syncing files with errors!!!")
        else:
            self.logger.info("finished syncing files on FTP server")


    def fix_permissions(self):
        """
        Make it possible for the data partners to retrieve the files.
        """

        args = self.SSH, self.USER, self.HOST, self.PATH
        command = '%s %s@%s "chmod -R 755 %s/full*"' % args
        self.logger.info("chmod command: %s", command)
        result = cdr.runCommand(command)
        if result.error:
            self.logger.info("*** Error:")
            self.logger.info(result.error)
            self.logger.info("finished fixing permissions with errors!!!")
        else:
            self.logger.info("finished fixing permissions on FTP server")

    def list_docs(self, base, doctype):
        """Create a set of the file names for a specified document type.
        """

        try:
            path = "%s/%s" % (base, doctype)
            os.chdir(path)
            filenames = set(glob.glob("CDR*"))
            self.logger.debug("%d docs in %s", len(filenames), path)
        except:
            self.logger.error("%s not found", path)
            filenames = set()
        return filenames

    def get_week(self):
        """Create the YYYYWW string for the job's ISO week.
        """

        if self.opts.week:
            return self.opts.week
        query = cdrdb.Query("pub_proc", "started")
        # query.where(query.Condition("id", self.opts.job))
        query.where(query.Condition("id", self.job_id))
        started = query.execute().fetchone()[0]
        year, week, dow = started.isocalendar()
        return "%04d%02d" % (year, week)

    def changed(self, doctype, name):
        """Compare a published file with last week's version.

        We can no longer use the Python library's filecmp module, as
        the Linux server did, because that reports all the files as
        having changed (because on Windows all of the os.stat results
        have changed).
        """

        oldpath = "%s/full/%s/%s" % (self.PUB_SHADOW, doctype, name)
        newpath = "%s/%s/%s" % (self.job_dir, doctype, name)
        return cmp(open(oldpath, "rb").read(), open(newpath, "rb").read())

    @staticmethod
    def extract_id(name):
        """Get the CDR document ID from the file name.

        We do this so we can sort the names correctly.
        """

        root, ext = os.path.splitext(name)
        return int(root[3:])

if __name__ == "__main__":
    """Make it possible to load this file as a module (e.g., for pylint).

    Don't log the parser's exit.
    """

    try:
        Control().run()
    except SystemExit:
        pass
    except:
        Control.LOGGER.exception("*** sftp-export-data.py failed!!!")
