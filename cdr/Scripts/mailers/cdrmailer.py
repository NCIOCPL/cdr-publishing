#----------------------------------------------------------------------
#
# $Id: cdrmailer.py,v 1.10 2002-02-14 20:21:18 ameyer Exp $
#
# Base class for mailer jobs
#
# $Log: not supported by cvs2svn $
# Revision 1.9  2002/02/06 00:23:30  ameyer
# Replaced stub latex converter with reference to the real thing.
#
# Revision 1.8  2002/01/23 17:13:14  bkline
# Temporary stubs to work around gaps in cdrxmllatex in Alan's absence.
#
# Revision 1.7  2001/10/22 23:57:42  bkline
# Added member field for subset name; moved core mailer code out to
# cdr module; added __buildName method.
#
# Revision 1.6  2001/10/11 19:48:22  bkline
# Added Address class; moved common sendMail() code out to cdr module.
#
# Revision 1.5  2001/10/09 12:06:25  bkline
# Changed __STAPLE_PROLOG to self.__STAPLE_PROLOG.
#
# Revision 1.4  2001/10/07 15:16:12  bkline
# Added getDeadline().
#
# Revision 1.3  2001/10/07 12:49:44  bkline
# Reduced use of publicly accessible members.  Enhanced docs.
#
# Revision 1.2  2001/10/06 23:43:12  bkline
# Changed parameters to makeLatex() method.  Added docs for fillQueue().
#
# Revision 1.1  2001/10/06 21:50:15  bkline
# Initial revision
#
#----------------------------------------------------------------------

import cdr, cdrdb, cdrxmllatex, os, re, sys, time, xml.dom.minidom

debugCtr = 1

#----------------------------------------------------------------------
# Object for managing mailer processing.
#----------------------------------------------------------------------
class MailerJob:
    """
    Base class for mailer job processing.  Cannot be used directly.
    Public methods include:

        run()
            Top-level method to invoke job processing.

        log(message)
            Appends progress or error information to logfile.

        fillQueue()
            Overridden by derived classes to define processing
            appropriate to each mailer type.  See documentation
            for this method below.

        addToQueue(job)
            Called by the derived classes' implementations of
            fillQueue() to add a PrintJob object to the print
            queue for the mailer job.

        addMailerTrackingDoc(doc, recipient, mailerType)
            Invoked by the derived classes' imlementations of
            fillQueue() to insert a Mailer document into the CDR.

        getCipsContactAddress(id)
            Returns an XML string containing an Address element
            for the ContactDetail information in a Person document
            identified as the CIPS contact address.

        makeLatex(doc, filters, mailType)
            Obtains a document from the repository, applies the
            caller's filters to it, and uses the cdrxmllatex
            module to generate the appropriate LaTeX source for
            the specified mailer type.

        makePS(latex, passCount, jobName, jobType)
            Takes the LaTeX source from an in-memory string and
            writes it out as converted PostScript, returning the
            new PrintJob object corresponding to the file.

        getId()
            Returns the ID for the publishing job.

        getSubset()
            Returns the string identifying the specific type
            of publishing job.

        getCursor()
            Returns object for executing database queries.

        getSession()
            Returns key for current CDR session.

        getDocIds()
            Returns the tuple of document IDs found in the
            pub_proc_doc table.

        getRecipients()
            Returns the dictionary containing the Recipient
            objects associated with this job.  Populated by
            the derived classes during the process of filling
            the print queue.  For jobs which use a single
            address for all packages sent to a given person,
            the Person document ID is used as the dictionary
            key.  For jobs in which different addresses can
            be used for the same person, the keys used for
            the dictionary are the fragment links which
            identify a person and a specific address, so
            the same person can appear more than once if
            multiple addresses are used.

        getDocuments()
            Returns the dictionary containing the Document objects
            for the documents which will be mailed out for this job.
            Populated by the derived classes during the process
            of filling the print queue.

        getParm(name)
            Returns a possibly empty tuple of values stored in
            the pub_proc_parm table for this job.  Filled
            by the base class.

        getDeadline()
            Returns a string in the form YYYY-MM-DD for the deadline
            by which the mailer must be responded to.
    """

    #------------------------------------------------------------------
    # Class-level values.
    #------------------------------------------------------------------
    __CDR_EMAIL     = "cdr@mmdb2.nci.nih.gov"
    __SMTP_RELAY    = "MAILFWD.NIH.GOV"
    __LOGFILE       = "d:/cdr/log/mailer.log"
    __DEF_PRINTER   = "\\\\CIPSFS1\\HP8100"
    __ERR_PATTERN   = re.compile("<Err>(.*)</Err>")
    __LATEX_OPTS    = "-halt-on-error -quiet -interaction batchmode "\
                      "-include-directory d:/cdr/mailers/style"

    #------------------------------------------------------------------
    # Constructor for base class.
    #------------------------------------------------------------------
    def __init__(self, jobId):
        """
        Parameters:
            jobId          - Integer for publication job number.
        """
        self.__id          = jobId
        self.__nMailers    = 0
        self.__docIds      = []
        self.__recipients  = {}
        self.__documents   = {}
        self.__parms       = {}
        self.__printer     = MailerJob.__DEF_PRINTER

    #------------------------------------------------------------------
    # Public access methods.
    #------------------------------------------------------------------
    def getId        (self): return self.__id
    def getCursor    (self): return self.__cursor
    def getSubset    (self): return self.__subset
    def getSession   (self): return self.__session
    def getDeadline  (self): return self.__deadline
    def getDocIds    (self): return self.__docIds
    def getRecipients(self): return self.__recipients
    def getDocuments (self): return self.__documents
    def addToQueue   (self, job):   self.__queue.append(job)
    def getParm      (self, name):
        v = self.__parms.get(name)
        return v and tuple(v) or ()

    #------------------------------------------------------------------
    # Driver for mailer job processing.
    #------------------------------------------------------------------
    def run(self):
        """
        Invokes the processing for a CDR mailer job.  Catches and
        logs all exceptions.  Returns 0 for success and 1 for failure.
        """
        try:
            self.log("******** starting mailer job ********")
            self.__loadSettings()
            self.__createQueue()
            self.fillQueue()
            self.__printQueue()
            self.__cleanup("Success", "Processed %d mailers" % self.__nMailers)
            self.log("******** finished mailer job ********")
            return 0
        except:
            (eType, eValue) = sys.exc_info()[:2]
            errMessage = eValue or eType
            self.log("ERROR: %s" % errMessage)
            self.__cleanup("Failure", errMessage)
            return 1

    #------------------------------------------------------------------
    # Append message to logfile.
    #------------------------------------------------------------------
    def log(self, message):
        """
        Appends progress or error information to a log file.  Each
        entry is stamped with the current date and time and the
        number of the current publication job.  No return value.
        No exceptions raised.
        """
        try:
            now = time.ctime(time.time())
            msg = "[%s] Job %d: %s" % (now, self.__id, message)
            open(MailerJob.__LOGFILE, "a").write(msg + "\n")
        except:
            pass

    #------------------------------------------------------------------
    # Placeholder for method to populate the print queue for the job.
    #------------------------------------------------------------------
    def fillQueue(self):
        """
        The primary responsibility of the classes derived from MailerJob
        is to provide a definition of this method.  This method must
        populate the object's print queue by invoking addToQueue() with
        instances of the PrintJob class, defined below.  Each PrintJob
        object must represent a file which is ready to be written
        directly to the printer (for example, PostScript, or plain text,
        but not RTF files or Microsoft Word documents).  Furthermore,
        for each copy of each document added to the print queue, the
        implementation of fillQueue() must invoke the addMailerTrackingDoc()
        method to add a new document to the repository for tracking the
        responses to the mailer.  The mailerType argument passed to that
        method must be a string which matches one of the valid values for
        MailerType enumerated in the schema for Mailer documents.

        The files created for the queue should be written to the
        current working directory (as should any intermediate working
        files), and the filenames provided to the constructor for the
        PrintJob objects should not include any path information.
        """
        raise "fillQueue() must be defined by derived class"

    #------------------------------------------------------------------
    # Generate a document for tracking a mailer.
    #------------------------------------------------------------------
    def addMailerTrackingDoc(self, doc, recipient, mailerType):
        """
        Parameters:
            doc         - Object of type Document, defined below
            recipient   - Object of type Recipient, defined below
            mailerType  - String containing a values matching the
                          list of valid values for MailerType
                          enumerated in the schema for Mailer docs.
        Return value:
            Integer ID for the newly inserted Mailer document.
        """

        recipId = "CDR%010d" % recipient.getId()
        docId   = "CDR%010d" % doc.getId()
        address = recipient.getAddress().getXml()
        xml     = """\
<CdrDoc Type="Mailer">
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr="cips.nci.nih.gov/cdr">
   <Type>%s</Type>
   <JobId>%d</JobId>
   <Recipient cdr:ref="%s">%s</Recipient>
   %s
   <Document cdr:ref="%s">%s</Document>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (docId, recipId, mailerType, self.__id, recipId, recipient.getName(),
       address, docId, doc.getTitle(), self.__now, self.__deadline)
        rsp   = cdr.addDoc(self.__session, doc = xml, checkIn = "Y", ver = "Y")
        match = self.__ERR_PATTERN.search(rsp)
        if match:
            err = match.group(1)
            raise "failure adding tracking document for %s: %s" % (docId, err)
        self.__nMailers += 1
        digits = re.sub("[^\d]", "", rsp)
        return int(digits)

    #------------------------------------------------------------------
    # Convert Unicode string to Latin-1 character set.
    #------------------------------------------------------------------
    def encodeLatin1(self, unicodeString):
        return unicodeString.encode('latin-1')

    #------------------------------------------------------------------
    # Retrieve the CIPS contact address for a mailer recipient.
    #------------------------------------------------------------------
    def getCipsContactAddress(self, id):
        """
        Parameters:
            doc         - Object of type Document, defined below
            id          - Integer ID for CDR Person document.
        Return value:
            Returns an XML string containing an Address element
            for the ContactDetail information in a Person document
            identified as the CIPS contact address.
        """
        docId   = cdr.normalize(id)
        filters = ["name:CIPS Contact Address"]
        result  = cdr.filterDoc(self.__session, filters, docId)
        if type(result) == type(""):
            raise "failure extracting contact address for %s: %s" % (
                docId,
                result)
        return Address(result[0])

    #------------------------------------------------------------------
    # Generate LaTeX source for a mailer document.
    #------------------------------------------------------------------
    def makeLatex(self, doc, filters, mailType, parms = []):
        """
        Parameters:
            doc         - Object of type Document, defined below
            filters     - List of names of filters to be applied
                          to the document's XML.
            mailType    - String used by the makeLatex() function
                          of the cdrxmllatex module to distinguish
                          between different mailer types produced
                          for this document's type; one of:
                                "initial"
                                "update"
                                "reminder"
            parms       - possibly empty set of parameters for filtering.
        Return value:
            Returns an object with the following methods:
                getLatex()          - reference to string with
                                      LaTeX source
                getLatexPassCount() - number of times to run
                                      the LaTeX processor on the
                                      source
                getStatus()         - 0 for success
                getMessages()       - tuple of informational or
                                      warning messages
        """

        # XXX Specify version when Mike's ready.
        docId = cdr.normalize(doc.getId())
        result = cdr.filterDoc(self.__session, filters, docId, parm = parms)
        if type(result) == type(""):
            raise "failure filtering document %s: %s" % (docId, result)
        try:
            global debugCtr
            fname = "%d.xml" % debugCtr
            debugCtr += 1
            open(fname, "w").write(result[0])
            docDom = xml.dom.minidom.parseString(result[0])
            return cdrxmllatex.makeLatex(docDom, doc.getDocType(),
                                         mailType, self.log)
        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue or eType
            raise "failure generating LaTeX for %s: %s" % (docId, eMsg)

    #------------------------------------------------------------------
    # Convert LaTeX to PostScript.
    #------------------------------------------------------------------
    def makePS(self, latex, passCount, basename, jobType):
        """
        Parameters:
            latex       - In-memory string containing LaTex source
                          for the current document.
            passCount   - Number of times the LaTeX processor must
                          be invoked for the document in order to
                          resolve such things as bibliographic
                          references.
            jobType     - Passed to the constructor for the new
                          PrintJob object.  Must be one of:
                                PrintJob.MAINDOC
                                PrintJob.COVERPAGE
        Return value:
            New PrintJob object representing the converted document.
        """

        try:

            # Save the LaTeX source.
            filename = basename + ".tex"
            open(filename, "w").write(latex)

            # Convert it to PostScript.
            for i in range(passCount):
                rc = os.system("latex %s %s" % (self.__LATEX_OPTS, filename))
                if rc:
                    raise "failure running LaTeX processor on %s" % filename
            rc = os.system("dvips -q %s" % basename)
            if rc:
                raise "failure running dvips processor on %s.dvi" % basename
            return PrintJob(basename + ".ps", jobType)

        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue or eType
            raise "failure converting %s.tex to %s.ps: %s" % (basename,
                                                              basename,
                                                              eMsg)

    #------------------------------------------------------------------
    # Prepare initial settings for job.
    #------------------------------------------------------------------
    def __loadSettings(self):
        self.__getDates()
        self.__getCdrSession()
        self.__getDbConnection()
        self.__loadDbInfo()

    #------------------------------------------------------------------
    # Calculate needed dates (now and two months from now).
    #------------------------------------------------------------------
    def __getDates(self):
        now             = time.localtime(time.time())
        deadline        = (now[0], now[1] + 2, now[2], 0, 0, 0, 0, 0, -1)
        deadline        = time.localtime(time.mktime(deadline))
        self.__now      = time.strftime("%Y-%m-%dT%H:%M:%S", now)
        self.__deadline = time.strftime("%Y-%m-%d", deadline)

    #------------------------------------------------------------------
    # Log into the CDR server.
    #------------------------------------------------------------------
    def __getCdrSession(self):
        rsp          = cdr.login("cdrmailers", "cdrmailers")
        match        = self.__ERR_PATTERN.search(rsp)
        if match:
            raise "CDR login failure: %s" % match.group(1)
        self.__session = rsp

    #------------------------------------------------------------------
    # Log into the CDR database.
    #------------------------------------------------------------------
    def __getDbConnection(self):
        try:
            self.__conn   = cdrdb.connect("CdrPublishing")
            self.__cursor = self.__conn.cursor()
        except cdrdb.Error, info:
            raise "database connection failure: %s" % info[1][0]

    #------------------------------------------------------------------
    # Load the settings for this job from the database.
    #------------------------------------------------------------------
    def __loadDbInfo(self):
        self.__getPubProcRow()
        self.__getPubProcDocRows()
        self.__getPubProcParmRows()

    #------------------------------------------------------------------
    # Load the row which matches this job from the pub_proc table.
    #------------------------------------------------------------------
    def __getPubProcRow(self):
        try:
            self.__cursor.execute("""\
                SELECT output_dir, email, pub_subset
                  FROM pub_proc
                 WHERE id = ?""", (self.__id,))
            row = self.__cursor.fetchone()
            if not row:
                raise "unable to find job %d" % self.__id
            (self.__outputDir, self.__email, self.__subset) = row
        except cdrdb.Error, info:
            raise "database error retrieving pub_proc row: %s" % info[1][0]

    #------------------------------------------------------------------
    # Load the list of document IDs (with version numbers) for this job.
    #------------------------------------------------------------------
    def __getPubProcDocRows(self):
        try:
            self.__cursor.execute("""\
                SELECT doc_id, doc_version
                  FROM pub_proc_doc
                 WHERE pub_proc = ?""", (self.__id,))
            self.__docList = self.__cursor.fetchall()
            if not self.__docList:
                raise "no documents found for job %d" % self.__id
            for doc in self.__docList:
                self.__docIds.append(doc[0])
            self.__docIds = tuple(self.__docIds)
        except cdrdb.Error, err:
            raise "database error retrieving pub_proc_doc rows: %s" % err[1][0]

    #------------------------------------------------------------------
    # Load the parameters stored in the pub_proc_parm table for this job.
    #------------------------------------------------------------------
    def __getPubProcParmRows(self):
        try:
            self.__cursor.execute("""\
                SELECT parm_name, parm_value
                  FROM pub_proc_parm
                 WHERE pub_proc = ?
              ORDER BY id""", (self.__id))
            rows = self.__cursor.fetchall()
            if rows:
                for row in rows:
                    if not self.__parms.has_key(row[0]):
                        self.__parms[row[0]] = []
                    self.__parms[row[0]].append(row[1])
                    if row[0] == "Printer":
                        self.__printer = row[1]
        except cdrdb.Error, info:
            raise "database error retrieving job parms: %s" % info[1][0]

    #------------------------------------------------------------------
    # Create and populate the print queue.
    #------------------------------------------------------------------
    def __createQueue(self):
        self.__queue = []
        try:
            os.chdir(self.__outputDir)
        except:
            raise "failure setting working directory to %s" % self.__outputDir

    #------------------------------------------------------------------
    # Print the jobs in the queue.
    #------------------------------------------------------------------
    def __printQueue(self):
        for job in self.__queue:
            job.Print(self.__printer, self.log)

    #------------------------------------------------------------------
    # Clean up.
    #------------------------------------------------------------------
    def __cleanup(self, status, message):
        try:
            self.__updateStatus(status, message)
            self.__sendMail()
            if self.__session: cdr.logout(self.__session)
        except:
            pass

    #------------------------------------------------------------------
    # Update the pub_proc table's status.
    #------------------------------------------------------------------
    def __updateStatus(self, status, message = None):
        try:
            if message:
                self.__cursor.execute("""\
                    UPDATE pub_proc
                       SET status = ?,
                           messages = ?,
                           completed = GETDATE()
                     WHERE id = ?""", (status, message, self.__id))
            else:
                self.__cursor.execute("""\
                    UPDATE pub_proc
                       SET status = ?,
                           completed = GETDATE()
                     WHERE id = ?""", (status, self.__id))
            self.__conn.commit()
        except:
            pass

    #------------------------------------------------------------------
    # Inform the user that the job has completed.
    #------------------------------------------------------------------
    def __sendMail(self):
        try:
            if self.__email:
                self.log("Sending mail to %s" % self.__email)
                sender  = MailerJob.__CDR_EMAIL
                subject = "CDR Mailer Job Status"
                message = """\
Job %d has completed.  You can view a status report for this job at:

    http://mmdb2.nci.nih.gov/cgi-bin/cdr/PubStatus.py?id=%d

Please do not reply to this message.
""" % (self.__id, self.__id)
                cdr.sendMail(sender, [self.__email], subject, message)
        except:
            self.log("failure sending email to %s: %s" % (self.__email,
                                                          cdr.exceptionInfo()))

#----------------------------------------------------------------------
# Object to hold a document to be sent to the printer.
#----------------------------------------------------------------------
class PrintJob:
    """
    Public members:

        MAINDOC
            Used for constructor's filetype parameter to identify
            a primary document which should be stapled if it is
            not too large.

        COVERPAGE
            Used for constructor's filetype parameter to identify
            an ancillary document which should not be stapled.

        Print()
            Writes the current print job to the specified printer.
    """
    MAINDOC       = 1
    COVERPAGE     = 2
    __PAGES_PATTERN = re.compile("%%Pages: (\\d+)")
    __MAX_STAPLED   = 25
    __STAPLE_PROLOG = """\
\033%-12345X@PJL
@PJL SET FINISH=STAPLE
@PJL SET STAPLEOPTION=ONE
@PJL SET OUTBIN=OPTIONALOUTBIN2
@PJL ENTER LANGUAGE=POSTSCRIPT
"""
    def __init__(self, filename, filetype):
        self.__filename = filename
        self.__filetype = filetype
        self.__staple   = 0
        if self.__filetype == PrintJob.MAINDOC:
            pages = None
            ps = open(self.__filename)
            while 1:
                line = ps.readline()
                match = PrintJob.__PAGES_PATTERN.match(line)
                if match:
                    pages = int(match.group(1))
                    break
            if not pages:
                raise "can't find page count in %s" % self.__filename
            if pages <= PrintJob.__MAX_STAPLED:
                self.__staple = 1
            ps.close()

    #------------------------------------------------------------------
    # Send the current print job to the specified printer.
    #------------------------------------------------------------------
    def Print(self, printer, logFunc):
        logFunc("printing %s %s" % (
            self.__filename,
            self.__staple and "(stapled)" or ""))

        prn = open(printer, "w")
        doc = open(self.__filename)
        prn.write((self.__staple and self.__STAPLE_PROLOG or "") +
                   doc.read())
        doc.close()
        prn.close()

#----------------------------------------------------------------------
# Object to hold information about a mailer organization.
#----------------------------------------------------------------------
class Org:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document
            for a recipient of this mailer.

        getName()
            Returns the value of the title column of the document table
            in the CDR database for a recipient of this mailer.
    """
    def __init__(self, id, name):
        self.__id      = id
        self.__name    = name
    def getId     (self): return self.__id
    def getName   (self): return self.__name

#----------------------------------------------------------------------
# Object to hold information about a mailer recipient.
#----------------------------------------------------------------------
class Recipient:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document
            for a recipient of this mailer.

        getName()
            Returns the value of the title column of the document table
            in the CDR database for a recipient of this mailer.

        getAddress()
            Returns the Address object used used for addressing the
            mailer to this recipient.

        getDocs()
            Returns the list of Document objects representing documents
            sent to this recipient.
    """
    def __init__(self, id, name, address = None):
        self.__id      = id
        self.__name    = name
        self.__address = address
        self.__docs    = []
    def getId     (self): return self.__id
    def getName   (self): return self.__name
    def getAddress(self): return self.__address
    def getDocs   (self): return self.__docs

#----------------------------------------------------------------------
# Object to hold information about a mailer document.
#----------------------------------------------------------------------
class Document:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document.

        getTitle()
            Returns the value of the title column of the document table
            in the CDR database.

        getDocType()
            Returns the name of this document's CDR document type (e.g.,
            "Summary").

    """
    def __init__(self, id, title, docType):
        self.__id         = id
        self.__title      = title
        self.__docType    = docType
    def getId     (self): return self.__id
    def getTitle  (self): return self.__title
    def getDocType(self): return self.__docType

#----------------------------------------------------------------------
# Object to hold information about a mailer address.
#----------------------------------------------------------------------
class Address:
    """
    Public methods:

        getAddressee()
            Returns concatenation of prefix, forename, and surname.

        getNumStreetLines()
            Returns the number of strings in the street address.

        getStreetLine(number)
            Returns the string for the street address, indexed from
            base of 0.

        getCity()
            Returns string for city of this address, if any; otherwise
            None.

        getCitySuffix()
            Returns the string for the city suffix for this address,
            if any; otherwise None.

        getState()
            Returns the name of the political unit for this address,
            if any; otherwise None.

        getCountry()
            Returns the string for the country for this address, if
            any; otherwise None.

        getPostalCode()
            Returns the postal code (ZIP code for US addresses) for
            this address, if any; otherwise None.

        getCodePosition()
            One of:
                "after City"
                "after Country"
                "after PoliticalUnit_State"
                "before City"
                None
    """

    #------------------------------------------------------------------
    # Constructor for CDR mailer Address object.
    #------------------------------------------------------------------
    def __init__(self, xmlFragment):
        """
        Parameters:
            xmlFragment    - Either DOM object for parsed address XML,
                             or the string containing the XML for the
                             address.
        """
        self.__addressee     = None
        self.__street        = []
        self.__city          = None
        self.__citySuffix    = None
        self.__state         = None
        self.__country       = None
        self.__postalCode    = None
        self.__codePos       = None
        if type(xmlFragment) == type("") or type(xmlFragment) == type(u""):
            dom = xml.dom.minidom.parseString(xmlFragment)
        else:
            dom = xmlFragment
        for node in dom.documentElement.childNodes:
            if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if node.nodeName == 'PostalAddress':
                    self.__parsePostalAddress(node)
                elif node.nodeName == 'Name':
                    self.__addressee = self.__buildName(node)

    #------------------------------------------------------------------
    # Public access methods.
    #------------------------------------------------------------------
    def getNumStreetLines (self): return len(self.__street)
    def getStreetLine(self, idx): return self.__street[idx]
    def getCity           (self): return self.__city
    def getCitySuffix     (self): return self.__citySuffix
    def getState          (self): return self.__state
    def getCountry        (self): return self.__country
    def getPostalCode     (self): return self.__postalCode
    def getCodePosition   (self): return self.__codePos
    def getAddressee      (self): return self.__addressee

    #------------------------------------------------------------------
    # Create XML string from address information.
    #------------------------------------------------------------------
    def getXml(self):
        xml = "<Address><PostalAddress>"
        for line in self.__street:
            xml += "<Street>%s</Street>" % line
        if self.__city:
            xml += "<City>%s</City>" % self.__city
        if self.__citySuffix:
            xml += "<CitySuffix>%s</CitySuffix>" % self.__citySuffix
        if self.__state:
            xml += "<PoliticalUnit_State>%s<SPoliticalUnit_Statetate>" \
                % self.__state
        if self.__country:
            xml += "<Country>%s</Country>" % self.__country
        if self.__postalCode:
            xml += "<PostalCode_ZIP>%s</PostalCode_ZIP>" % self.__postalCode
        if self.__codePos:
            xml += "<CodePosition>%s</CodePosition>" % self.__codePos
        return xml + "</PostalAddress></Address>"

    #------------------------------------------------------------------
    # Extract postal address element values.
    #------------------------------------------------------------------
    def __parsePostalAddress(self, node):
        for child in node.childNodes:
            if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if child.nodeName == "Street":
                    self.__street.append(cdr.getTextContent(child))
                elif child.nodeName == "City":
                    self.__city = cdr.getTextContent(child)
                elif child.nodeName == "CitySuffix":
                    self.__citySuffix = cdr.getTextContent(child)
                elif child.nodeName == "PoliticalUnit_State":
                    self.__state = cdr.getTextContent(child)
                elif child.nodeName == "Country":
                    self.__country = cdr.getTextContent(child)
                elif child.nodeName == "PostalCode_ZIP":
                    self.__postalCode = cdr.getTextContent(child)
                elif child.nodeName == "CodePosition":
                    self.__codePos = cdr.getTextContent(child)

    #------------------------------------------------------------------
    # Construct name string from components.
    #------------------------------------------------------------------
    def __buildName(self, node):
        givenName = None
        surname   = None
        prefix    = None
        for child in node.childNodes:
            if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if child.nodeName == "GivenName":
                    surname = cdr.getTextContent(child)
                elif child.nodeName == "SurName":
                    givenName = cdr.getTextContent(child)
                elif child.nodeName == "Prefix":
                    prefix = cdr.getTextContent(child)
        name = ""
        if prefix: name += prefix + " "
        if givenName: name += givenName + " "
        if surname: name += surname
        name = name.strip()
        return name
