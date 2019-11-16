"""
Process a portion of a queued publishing job
"""

import argparse
import os
import time
from lxml import etree
try:
    from cdrapi import db as cdrdb
except:
    time.sleep(5)
    try:
        from cdrapi import db as cdrdb
    except:
        time.sleep(10)
        from cdrapi import db as cdrdb
from cdrapi.docs import Doc
from cdrapi.settings import Tier
from cdrapi.users import Session


class Control:
    """
    Top-level object for CDR publishing job processing
    """


    def __init__(self, session, job_id, spec_id, *docs, **opts):
        """
        Fetch information for this run from the database
        """

        self.session = Session(session)
        self.opts = opts
        self.job_id = job_id
        query = cdrdb.Query("export_spec", "filters", "subdir")
        query.where(query.Condition("job_id", job_id))
        query.where(query.Condition("spec_id", spec_id))
        row = query.execute(self.cursor).fetchone()
        self.filters = eval(row.filters)
        self.subdir = row.subdir
        self.docs = []
        for d in docs:
            doc_id, doc_version = d.split("/")
            opts = dict(id=doc_id, version=doc_version)
            if doc_version == "lastp":
                opts["before"] = self.job_start
            self.docs.append(Doc(self.session, **opts))

    def run(self):
        """
        Export the documents assigned to this invocation
        """

        select = """\
            SELECT doc_id FROM pub_proc_doc
             WHERE pub_proc = ?
               AND doc_id = ?"""
        insert = """\
            INSERT INTO pub_proc_doc (pub_proc, doc_id, doc_version, subdir)
                 VALUES (?, ?, ?, ?)"""
        update = """\
            UPDATE pub_proc_doc
               SET failure = ?, messages = ?
             WHERE pub_proc = ?
               AND doc_id = ?"""
        for doc in self.docs:
            self.logger.info("Exporting %s", doc.cdr_id)
            self.cursor.execute(select, (self.job_id, doc.id))
            row = self.cursor.fetchone()
            if not row:
                values = self.job_id, doc.id, doc.version, self.subdir
                self.cursor.execute(insert, values)
                self.conn.commit()
            try:
                warnings = self.export_doc(doc)
                if warnings:
                    values = None, repr(warnings), self.job_id, doc.id
                    self.cursor.execute(update, values)
                    self.conn.commit()
            except Exception as e:
                errors = e.args
                self.logger.exception("%s export failed", doc.cdr_id)
                values = "Y", repr(errors), self.job_id, doc.id
                self.cursor.execute(update, values)
                self.conn.commit()

    def export_doc(self, doc):
        """
        Filter and store a CDR document in the file system

        Pass:
          doc - reference to `Doc` object
        """

        filename = doc.export_filename
        if self.opts.get("level") == "DEBUG":
            print((doc.cdr_id))
        directory = self.work_dir
        if self.subdir:
            directory += "/{}".format(self.subdir)
        if doc.doctype.name == "Media":
            self.write_doc(doc.blob, directory, filename)
            blob_date = str(doc.blob_date)[:10]
            title = doc.title.replace("\r", "").replace("\n", " ")
            values = self.job_id, doc.id, filename, blob_date, title.strip()
            query = cdrdb.Query("media_manifest", "doc_id")
            query.where(query.Condition("job_id", self.job_id))
            query.where(query.Condition("doc_id", doc.id))
            row = query.execute(self.cursor).fetchone()
            if not row:
                self.cursor.execute("""\
        INSERT INTO media_manifest (job_id, doc_id, filename, blob_date, title)
             VALUES (?, ?, ?, ?, ?)""", values)
                self.conn.commit()
        else:
            filtered_doc = self.filter_doc(doc)
            errors = None
            if self.validating:
                errors = self.validate_doc(filtered_doc.result_tree)
                if errors:
                    messages = [error.message for error in errors]
                    directory = self.work_dir + "/InvalidDocs"
            xml = etree.tostring(filtered_doc.result_tree, encoding="utf-8")
            if xml is None:
                xml = bytes(filtered_doc.result_tree)
            else:
                xml = xml.replace(b"\r", b"").strip() + b"\n"
            self.write_doc(xml, directory, filename)
            if errors:
                raise Exception(messages)
            return filtered_doc.warnings

    def filter_doc(self, doc):
        """
        Transform a CDR document to its exportable structure

        Pass:
          doc - reference to `Doc` object to be transformed

        Return:
          reference to `FilteredDoc` object
        """

        root = None
        first_pub = doc.first_pub
        if not first_pub and doc.first_pub_knowable:
            first_pub = self.job_start
        warnings = []
        for filters, parameters in self.filters:
            parms = dict(parameters)
            if "DateFirstPub" in parms and first_pub:
                parms["DateFirstPub"] = str(first_pub)[:10]
                parms["pubProcDate"] = str(self.job_start)[:10]
            opts = dict(parms=parms, doc=root, date=str(self.job_start))
            result = doc.filter(*filters, **opts)
            warnings += result.messages
            root = result.result_tree
        if warnings:
            self.logger.warning("CDR%d: %r", doc.id, warnings)
        return self.FilteredDoc(root, warnings)

    def validate_doc(self, doc):
        """
        Validate a filtered CDR document against its DTD

        Pass:
          doc - top-level node for filtered document

        Return:
          result of validation operation
        """

        with open(self.dtd_path) as fp:
            dtd = etree.DTD(fp)
        if isinstance(doc, (str, bytes)):
            doc = etree.fromstring(doc)
        dtd.validate(doc)
        return dtd.error_log.filter_from_errors()

    def write_doc(self, doc_bytes, directory, filename):
        """
        Store an exported CDR document in the file system

        Pass:
          doc_bytes - document representation to be stored
          directory - path to location of file
          filename - string for name of file to be created
        """

        if self.no_output:
            return
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except:
                self.logger.exception("Failure creating %s", directory)
                pass
        with open("{}/{}".format(directory, filename), "wb") as fp:
            fp.write(doc_bytes)

    # ------------------------------------------------------------------
    # PROPERTIES START HERE.
    # ------------------------------------------------------------------

    @property
    def conn(self):
        """
        Connection to the CDR database
        """

        if not hasattr(self, "_conn"):
            opts = dict(user="CdrPublishing")
            self._conn = cdrdb.connect(**opts)
        return self._conn

    @property
    def cursor(self):
        """
        Database `Cursor` object
        """

        if not hasattr(self, "_cursor"):
            self._cursor = self.conn.cursor()
        return self._cursor

    @property
    def dtd_path(self):
        """
        Location of DTD file to be used for validation
        """

        if not hasattr(self, "_dtd_path"):
            query = cdrdb.Query("pub_proc_parm", "parm_value")
            query.where(query.Condition("pub_proc", self.job_id))
            query.where("parm_name = 'DTDFileName'")
            row = query.execute(self.cursor).fetchone()
            filename = row.parm_value if row else "pdqCG.dtd"
            args = self.tier.drive, filename
            self._dtd_path = "{}:/cdr/Licensee/{}".format(*args)
        return self._dtd_path

    @property
    def failure_dir(self):
        """
        String for path to which output directory is renamed on failure
        """

        output_dir = self.output_dir
        if output_dir:
            return output_dir + ".FAILURE"
        return None

    @property
    def job_start(self):
        """
        Date/time the export job was created (so a bit of a misnomer)
        """

        if not hasattr(self, "_job_start"):
            query = cdrdb.Query("pub_proc", "started")
            query.where(query.Condition("id", self.job_id))
            self._job_start = query.execute(self.cursor).fetchone().started
        return self._job_start

    @property
    def logger(self):
        """
        Standard library `Logger` object
        """

        if not hasattr(self, "_logger"):
            opts = dict(level=self.opts.get("level") or "INFO")
            self._logger = self.tier.get_logger("export-docs", **opts)
        return self._logger

    @property
    def no_output(self):
        """
        Flag indicating that document output won't be written to disk
        """

        if not hasattr(self, "_no_output"):
            self._no_output = False
            query = cdrdb.Query("pub_proc", "no_output")
            query.where(query.Condition("id", self.job_id))
            row = query.execute(self.cursor).fetchone()
            if row and row.no_output == "Y":
                self._no_output = True
        return self._no_output

    @property
    def output_dir(self):
        """
        Final path name for exported documents' location
        """

        if not hasattr(self, "_output_dir"):
            self._output_dir = self.opts.get("output-dir")
        if not self._output_dir:
            query = cdrdb.Query("pub_proc", "output_dir")
            query.where(query.Condition("id", self.job_id))
            self._output_dir = query.execute(self.cursor).fetchone().output_dir
        return self._output_dir

    @property
    def tier(self):
        """
        Identification of which CDR server is running the publishing job
        """

        if not hasattr(self, "_tier"):
            self._tier = Tier()
        return self._tier

    @property
    def validating(self):
        """
        Flag indicating whether we should validate the docs against a DTD
        """

        if not hasattr(self, "_validating"):
            query = cdrdb.Query("pub_proc_parm", "parm_value")
            query.where(query.Condition("pub_proc", self.job_id))
            query.where("parm_name = 'ValidateDocs'")
            row = query.execute(self.cursor).fetchone()
            self._validating = row and row.parm_value == "Yes"
        return self._validating

    @property
    def work_dir(self):
        """
        Temporary name for job output while we are exporting
        """

        output_dir = self.output_dir
        if output_dir:
            return output_dir + ".InProcess"
        return None


    class FilteredDoc:
        """
        Results of a sequence of XSL/T filtering operations

        Instance attributes:
          result_tree - reference to `_XSLTResultTree` object
          warnings - possibly empty sequence of warning strings
        """

        def __init__(self, result_tree, warnings):
            """
            Wrap the object's attributes
            """

            self.result_tree = result_tree
            self.warnings = warnings

def main():
    """
    Test driver
    """

    opts = dict(level="INFO")
    parser = argparse.ArgumentParser()
    parser.add_argument("session")
    parser.add_argument("job")
    parser.add_argument("spec")
    parser.add_argument("docs", nargs="*")
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()
    if args.debug:
        opts["level"] = "DEBUG"
    if args.output:
        opts["output-dir"] = args.output
    Control(args.session, args.job, args.spec, *args.docs, **opts).run()

if __name__ == "__main__":
    """
    Let this be loaded as a module without doing anything
    """

    main()
