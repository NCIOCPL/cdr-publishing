#!d:/Python/python.exe
"""
Copy published data to the public SFTP directory.

Replacement for FtpExportData.py, which created a tar file of the
latest publishing output directory and copied it to an FTP server.
This version installs the PDQ files directly on the storage exposed
by the sFTP server using rsync.

JIRA::OCECDR-4348 - use checksums to detect changed files
"""

from argparse import ArgumentParser
from datetime import datetime
from functools import partial
from glob import glob
from hashlib import sha256
import os
import re
import shutil
import tarfile
from lxml import etree
import cdr
from cdrapi import db

class Control:
    """
    Wrap the processing logic in a single namespace.

    Properties:
        job_id - ID of the most recent licensee job
        job_ids - IDs of all of the licensee jobs, sorted chronologically
        job_path - location of the filtered CDR documents
        logger - object for writing to the log file
        newsums - nested dictionary of checksums for docs we're transferring
        oldsums - nested dictionary of checksums for docs already transferred
        prev_job_id - ID of the job we transferred the last time
        prev_job_path - location of documents transferred by the last run
        opts - command-line argument values controlling runtime options
        types - sequence of exported document types
        week - YYYYWW string representing the ISO week
    """

    CHECKSUMS = "CHECKSUMS"
    LICENSEE_DOCS = "d:/cdr/Output/LicenseeDocs"
    PUB_SHADOW = "d:/cdr/sftp_shadow"
    PUB_SHADOW_FULL = "{}/full".format(PUB_SHADOW)
    LANGUAGES = dict(English="en", Spanish="es")
    MEDIA_CATALOG = "media_catalog.txt"
    LOGGER = cdr.Logging.get_logger("sftp-export")
    SSH = ("d:/cygwin/bin/ssh.exe -i d:/etc/cdroperator_rsa "
           "-o LogLevel=error "
           "-o StrictHostKeyChecking=no")
    TIER = cdr.Tier()
    HOST = TIER.hosts["SFTP"]
    USER = "cdroperator"
    PATH = "/sftp/sftphome/cdrstaging/pdq-{}".format(TIER.name.lower())

    def __init__(self):
        """Log what we're about to do."""
        self.logger.info(47 * "*")
        self.logger.info("sftp-export-data.py - Started")
        self.logger.info(47 * "*")
        self.logger.info("Processing %s", self.job_path)
        self.logger.info("week %s", self.week)
        self.logger.info("path is %s", os.environ.get("PATH"))

    def run(self):
        """
        Execute the top-level processing for the script, performing 4 tasks.

           1. Create catalog files for what we're publishing.
           2. Create compressed archives for the files.
           3. Stage the files to be synced.
           4. Populate the public sFTP data share.
        """

        start = datetime.now()
        os.chdir(self.job_path)

        # Optionally skip the first three steps if so requested.
        if not self.opts.push_only:

            # 1. Creating tar files and auxilliary files.
            if not self.opts.skip_catalogs:
                self.create_catalogs()

            # 2. Create tar files.
            self.create_archives()

            # 3. Copy files and move tar files to shadow location.
            self.copy_files()

        # 4. Sync the staging area to the sFTP server.
        if not self.opts.create_only:
            self.push_files()
            self.fix_permissions()

        elapsed = (datetime.now() - start).total_seconds()
        self.logger.info("")  # Blank line to format log output
        self.logger.info("completed in %f seconds", elapsed)

        self.logger.info(47 * "*")
        self.logger.info("sftp-export-data.py - Finished")
        self.logger.info(47 * "*")

    def create_catalogs(self):
        """
        Compare what we published last week with what we're publishing now.

        Creates a summary file listing counts for added, removed, and changed
        files of each document type. Also, for each document type for which
        any such differences have occurred since the previous week, creates
        a manifest, listing each document, with the action behind the
        difference.
        """

        for path in glob("{}/*.{}".format(self.job_path, self.week)):
            self.logger.debug("removing %r", path)
            os.remove(path)
        changes = []
        self.logger.info("Processing doctype directories:")
        for doctype in self.types:
            self.logger.info("...processing %s", doctype)
            oldsums = self.oldsums.get(doctype, {})
            newsums = self.newsums.get(doctype, {})
            olddocs = set(oldsums)
            newdocs = set(newsums)
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
                if oldsums[name] != newsums[name]:
                    changed += 1
                    docs.append((self.extract_id(name), name, "modified"))
            if docs:
                path = "{}/{}.{}".format(self.job_path, doctype, self.week)
                with open(path, "w") as fp:
                    for doc_id, name, action in sorted(docs):
                        fp.write("{}:{}\n".format(name, action))
                self.logger.debug("%d line(s) in %s", len(docs), path)
            prefix = "{}.{}".format(doctype, self.week)
            changes.append("{}:added:{:d}\n".format(prefix, len(added)))
            changes.append("{}:removed:{:d}\n".format(prefix, len(dropped)))
            changes.append("{}:modified:{:d}\n".format(prefix, changed))
            if doctype == "Summary":
                self.catalog_summaries(newdocs)
        with open("{}/{}.changes".format(self.job_path, self.week), "w") as fp:
            for change in sorted(changes):
                fp.write(change)
        self.logger.info("catalogs created")

    def catalog_summaries(self, filenames):
        """
        Create Summary.en and Summary.es catalog files.

        Each file lists the file names (one per line) of each of the summary
        documents in the language of the catalog file.
        """

        summaries = dict(en=[], es=[])
        for filename in filenames:
            language = self.get_summary_language(filename)
            summaries[language].append((self.extract_id(filename), filename))
        for language in summaries:
            args = self.job_path, language
            with open("{}/Summary.{}".format(*args), "w") as fp:
                for doc_id, filename in sorted(summaries[language]):
                    fp.write("{}\n".format(filename))
        self.logger.info("cataloged summaries by language")

    def get_summary_language(self, filename):
        """
        Parse the summary document to determine its language.

        Pass:
          filename - string naming the file to examine
        """

        path = "{}/Summary/{}".format(self.job_path, filename)
        root = etree.parse(path).getroot()
        language = cdr.get_text(root.find("SummaryMetaData/SummaryLanguage"))
        return self.LANGUAGES[language]

    def create_archives(self):
        """
        Create compressed archives for the published files.

        A tar file is created for each of the document types.
        In addition, a complete tar file is created containing
        all of the document types, as well as the catalogs
        created above.
        """
        self.logger.info("")  # Blank line to format log output
        self.logger.info("Creating full.tar.gz")
        os.chdir(self.job_path)
        with tarfile.open("full.tar.gz", "w:gz") as tar:
            for name in self.types:
                self.logger.info("...adding %s", name)
                tar.add(name)
                catalog_name = "{}.{}".format(name, self.week)
                if os.path.exists(catalog_name):
                    tar.add(catalog_name)
                if name == "Summary":
                    tar.add("Summary.en")
                    tar.add("Summary.es")
            if os.path.exists(self.MEDIA_CATALOG):
                tar.add(self.MEDIA_CATALOG)
            tar.add("{}.changes".format(self.week))
        self.logger.info("")
        self.logger.info("Creating doctype tar files:")
        for name in self.types:
            tarname = "{}.tar.gz".format(name)
            with tarfile.open(tarname, "w:gz") as tar:
                self.logger.info("...creating %s.tar.gz", name)
                tar.add(name)

    def copy_files(self):
        """
        Populate the local sFTP shadow directory.

        Copy the individual document files and catalogs to the shadow
        directory, and move the compressed archive files to that
        location.
        """

        self.logger.info("")  # Blank line to format log output
        self.logger.info("Copying files to shadow location")
        os.chdir(self.job_path)
        destination = "{}/full.tar.gz".format(self.PUB_SHADOW)
        try:
            os.remove(destination)
        except:
            print(("Can't remove {}".format(destination)))
        shutil.move("full.tar.gz", destination)
        full = self.PUB_SHADOW_FULL
        shutil.rmtree(full, ignore_errors=True)
        os.mkdir(full)
        shutil.copy("{}.changes".format(self.week), full)
        if os.path.exists(self.MEDIA_CATALOG):
            shutil.copy(self.MEDIA_CATALOG, full)
        for name in self.types:
            destination = "{}/{}".format(full, name)
            self.logger.info("...copying %s", name)
            shutil.copytree(name, destination)
            args = "{}.tar.gz".format(name), "{}.tar.gz".format(destination)
            shutil.move(*args)
            catalog_name = "{}.{}".format(name, self.week)
            if os.path.exists(catalog_name):
                shutil.copy(catalog_name, full)
            if name == "Summary":
                shutil.copy("Summary.en", full)
                shutil.copy("Summary.es", full)

    def push_files(self):
        """
        Update the sFTP server with the content of the shadow directory.

        Use `rsync` to get the the individual document files and catalogs
        from the shadow directory to the sFTP server.
        """

        args = self.SSH, self.USER, self.HOST, self.PATH
        command = 'rsync --delete -rae "{}" full* {}@{}:{}'.format(*args)
        self.logger.info("")  # Blank line to format log output
        self.logger.info("ssh host: %s", self.HOST)
        self.logger.debug("ssh user: %s", self.USER)
        self.logger.info("rsync command: %s", command)

        os.chdir(self.PUB_SHADOW)

        result = cdr.run_command(command)
        self.logger.info("")  # Blank line to format log output
        self.logger.info("*** run_command output")
        self.logger.info(result.stdout)

        if result.stderr:
            self.logger.info("*** Error:")
            self.logger.info(result.stderr)
            self.logger.info("finished syncing files with errors!!!")
        else:
            self.logger.info("finished syncing files on FTP server")

        os.chdir(self.job_path)

    def load_checksums(self, persist=True):
        """
        Get the checksums for the CDR documents in the job tree.

        Assumes we have already made the current working directory
        the top-level directory for the job.

        If the checksums have already been calculated (as will typically
        be the case for the previous week's files), just load them from
        the file where they have been persisted.

        Pass:
            persist - if True (the default), save the calculated checksums
                      to save us from having to calculate the sums for this
                      job's files in a subsequent run

        Return:
            nested dictionary of checksums, top level indexed by document
            type name, inner dictionaries indexed by file name, with values
            of hex strings for SHA256 digest hashes
        """

        checksums = {}
        if os.path.exists(self.CHECKSUMS):
            with open(self.CHECKSUMS) as fp:
                for line in fp:
                    checksum, path = line.strip().split(None, 1)
                    directory, filename = path.split("/")
                    if directory not in checksums:
                        checksums[directory] = {}
                    checksums[directory][filename] = checksum
        else:
            for directory in self.types:
                sums = checksums[directory] = {}
                for path in glob("{}/CDR*".format(directory)):
                    filename = os.path.split(path)[-1]
                    sums[filename] = self.checksum(path)
                opts = len(sums), directory
                self.logger.debug("calculated %d checksums for %s files", *opts)
            if persist:
                with open(self.CHECKSUMS, "w") as fp:
                    for directory in sorted(checksums):
                        sums = checksums[directory]
                        for filename in sorted(sums, key=self.extract_id):
                            checksum = sums[filename]
                            path = "{}/{}".format(directory, filename)
                            fp.write("{} {}\n".format(checksum, path))
        return checksums

    def fix_permissions(self):
        """Make it possible for the data partners to retrieve the files."""
        args = self.SSH, self.USER, self.HOST, self.PATH
        command = '{} {}@{} "chmod -R 755 {}/full*"'.format(*args)
        self.logger.info("chmod command: %s", command)
        result = cdr.run_command(command)
        if result.stderr:
            self.logger.info("*** Error:")
            self.logger.info(result.stderr)
            self.logger.info("finished fixing permissions with errors!!!")
        else:
            self.logger.info("finished fixing permissions on FTP server")

    @property
    def job_id(self):
        """
        Get the overridden or calculated ID of the last licensee job.

        Use the job ID passed as a specific option if available; else
        use the default of the last job ID found in the LicenseeDocs
        directory.
        """

        if not hasattr(self, "_job_id"):
            if self.opts.job:
                self._job_id = self.opts.job
            else:
                self._job_id = self.job_ids[-1]
        return self._job_id

    @property
    def job_ids(self):
        """
        Collect all of the job IDS in the LicenseeDocs directory.

        If we don't find at least one job, there's nothing to transfer,
        so we'll bail.
        """

        if not hasattr(self, "_job_ids"):
            os.chdir(self.LICENSEE_DOCS)
            job_ids = set()
            for name in glob("Job*"):
                match = re.match(r"^Job(\d+)$", name)
                if match:
                    job_ids.add(int(match.group(1)))
            if not job_ids:
                self.logger.info("*** Error: No PDQ partner data found")
                exit(1)
            self._job_ids = sorted(job_ids)
            os.chdir(self.job_path)
        return self._job_ids

    @property
    def job_path(self):
        """Get the location of the documents to be transferred."""
        if not hasattr(self, "_job_path"):
            args = self.LICENSEE_DOCS, self.job_id
            self._job_path = "{}/Job{:d}".format(*args)
        return self._job_path

    @property
    def logger(self):
        """Adjust the logging level as requested."""
        if not hasattr(self, "_logger"):
            self._logger = Control.LOGGER
            self._logger.setLevel(self.opts.level.upper())
        return self._logger

    @property
    def newsums(self):
        """Get checksums for the documents we are about to transfer."""
        if not hasattr(self, "_newsums"):
            os.chdir(self.job_path)
            self._newsums = self.load_checksums()
            self.logger.info("loaded new checksums from %s", self.job_path)
        return self._newsums

    @property
    def oldsums(self):
        """
        Get checksums for the documents we transferred last time.

        Get them from the previous job directory if available.
        Otherwise get them from the shadow SFTP directory.
        """

        if not hasattr(self, "_oldsums"):
            directory = self.prev_job_path or self.PUB_SHADOW_FULL
            os.chdir(directory)
            self._oldsums = self.load_checksums()
            os.chdir(self.job_path)
            self.logger.info("loaded old checksums from %s", directory)
        return self._oldsums

    @property
    def opts(self):
        """Collect the command-line arguments."""
        if not hasattr(self, "_opts"):
            parser = ArgumentParser()
            parser.add_argument("--job", type=int,
                                help="enter job-id to process, default: last")
            parser.add_argument("--level", default="info",
                                help="specify log level "
                                "(debug, warn, [info], error)")
            parser.add_argument("--push-only", action="store_true",
                                help="copy the latest existing data set")
            parser.add_argument("--create-only", action="store_true",
                                help="create a new data set but do not copy")
            parser.add_argument("--skip-catalogs", action="store_true",
                                help="skip creating auxilliary files")
            parser.add_argument("--week",
                                help="use at your own risk")
            self._opts = parser.parse_args()
        return self._opts

    @property
    def prev_job_id(self):
        """
        Get the ID of the job whose documents we transferred the last time.

        Return None if there are no jobs found older than the one we are
        transferring.
        """

        if not hasattr(self, "_prev_job_id"):
            if len(self.job_ids) > 1:
                self._prev_job_id = self.job_ids[-2]
            else:
                self._prev_job_id = None
        return self._prev_job_id

    @property
    def prev_job_path(self):
        """Get the location of documents we transferred the last time."""
        if not hasattr(self, "_prev_job_path"):
            if self.prev_job_id is None:
                self._prev_job_path = None
            else:
                args = self.LICENSEE_DOCS, self.prev_job_id
                self._prev_job_path = "{}/Job{:d}".format(*args)
        return self._prev_job_path

    @property
    def types(self):
        """Get the names of the document types we're transferring."""
        if not hasattr(self, "_types"):
            os.chdir(self.job_path)
            types = [name for name in os.listdir(".") if os.path.isdir(name)]
            self._types = types
        return self._types

    @property
    def week(self):
        """Get the YYYYWW string for the job's ISO week."""
        if not hasattr(self, "_week"):
            self._week = self.opts.week
            if not self._week:
                query = db.Query("pub_proc", "started")
                query.where(query.Condition("id", self.job_id))
                started = query.execute().fetchone().started
                year, week, dow = started.isocalendar()
                self._week = "{:04d}{:02d}".format(year, week)
        return self._week

    @staticmethod
    def checksum(path):
        """
        Create a checksum for the bytes of a file.

        Use of checksums instead of loading the old and new files into
        memory and comparing them speeds up the catalog generation from
        5 1/2 minutes to 1 1/2 minutes on the CDR DEV server. This also
        avoids problems with aborted runs as reported in OCECDR-4348.

        We're using SHA256 instead of SHA-1 because Linus is planning
        to switch `git` from SHA-1 hashes to SHA256 hashes, and if
        SHA-1 isn't good enough for avoiding collisions in his view,
        then who are we to second-guess his judgment?

        Pass:
            path - string for relative path of file to checksum

        Return:
            Hex representation for SHA256 hash of file contents
        """

        hasher = sha256()
        with open(path, "rb") as fp:
            for block in iter(partial(fp.read, 4096), b""):
                hasher.update(block)
        return hasher.hexdigest()

    @staticmethod
    def extract_id(name):
        """
        Get the CDR document ID from the file name.

        Note:
            We do this so we can sort the names correctly.

        Pass:
           name - string for the file's name

        Return:
           integer extracted from the name
        """

        root, ext = os.path.splitext(name)
        return int(root[3:])

if __name__ == "__main__":
    """
    Make it possible to load this file as a module (e.g., for pylint).

    Don't log the parser's exit.
    """

    try:
        Control().run()
    except SystemExit:
        pass
    except:
        Control.LOGGER.exception("*** sftp-export-data.py failed!!!")
