#----------------------------------------------------------------------
#
# $Id: cdrmailer.py,v 1.42 2003-02-11 21:29:26 bkline Exp $
#
# Base class for mailer jobs
#
# $Log: not supported by cvs2svn $
# Revision 1.41  2003/01/28 16:15:33  bkline
# Replaced gzip and zip with tar/bzip2.
#
# Revision 1.40  2002/11/09 16:55:32  bkline
# Added code to package files after the job has completed.
#
# Revision 1.39  2002/11/08 22:41:14  bkline
# Added utf-8 encoding for mailer tracking document's XML.
#
# Revision 1.38  2002/11/08 17:25:49  bkline
# Fixed error check for return from filterDoc().
#
# Revision 1.37  2002/11/05 16:46:40  ameyer
# Fixed bug in getAddressLines() by removing obsolete reference to org.
#
# Revision 1.36  2002/10/31 19:59:09  bkline
# Fixed AddressLine bug.
#
# Revision 1.35  2002/10/25 14:21:53  bkline
# Fixed typo in method to generate address XML.
#
# Revision 1.34  2002/10/24 22:22:42  ameyer
# Made getOrganizationAddress() public.
# Fixed bug in call to filterDoc parameter.
#
# Revision 1.33  2002/10/24 21:34:15  bkline
# Pulled throttle, which has been moved to web interface.
#
# Revision 1.32  2002/10/24 17:51:35  bkline
# Adjustment to remailerFor parameter.
#
# Revision 1.31  2002/10/24 17:18:44  bkline
# Added remailerFor to addMailerTrackingDoc().
#
# Revision 1.30  2002/10/24 02:37:48  bkline
# Turned on doc versions; removed org type.
#
# Revision 1.29  2002/10/23 22:06:12  bkline
# Added org type to Org class.
#
# Revision 1.28  2002/10/23 11:44:08  bkline
# Fixed printer opening code.
#
# Revision 1.27  2002/10/23 03:33:14  ameyer
# Added code to get proper Organization address.
# Replaced some code with calls to new cdr.getQueryTermValueForId().
#
# Revision 1.26  2002/10/22 18:10:22  bkline
# Changed mailing label to use fixed-pitch font and to word-wrap long lines.
#
# Revision 1.25  2002/10/18 11:46:08  bkline
# Moved address formatting to Address object.
#
# Revision 1.24  2002/10/16 18:07:36  bkline
# Fixed typo in tags for state name in XML for address.
#
# Revision 1.23  2002/10/14 12:47:23  bkline
# Made actual mailer printing a separate batch job.
#
# Revision 1.22  2002/10/10 17:44:44  bkline
# Added PrintJob.PLAIN.
#
# Revision 1.21  2002/10/10 13:43:41  bkline
# Added __NONSTAPLE_PROLOG.
#
# Revision 1.20  2002/10/09 20:40:09  bkline
# Dropped obsolete includeCountry argument for assembling address lines.
#
# Revision 1.19  2002/10/09 19:41:46  bkline
# Added code to drop country line for domestic address labels.
#
# Revision 1.18  2002/10/09 18:09:15  bkline
# Added new code for generating LaTeX for address label sheet.
#
# Revision 1.17  2002/10/09 02:01:55  ameyer
# Changes in address generation based on new filters and new XML for
# addresses returned from the server.
#
# Revision 1.16  2002/10/08 13:56:23  ameyer
# Changes to logging, exception handling, directory creation.
#
# Revision 1.15  2002/10/08 01:39:00  bkline
# Fixed address parsing to match Lakshmi's new rules and to pick up
# additional information.  Added optional flag to suppress printing.
#
# Revision 1.14  2002/09/26 18:28:01  ameyer
# Replaced "mmdb2" with socket.gethostname().
#
# Revision 1.13  2002/09/12 23:29:51  ameyer
# Removed common routine from individual mailers to cdrmailer.py.
# Added a few trace statements.
#
# Revision 1.12  2002/05/15 01:40:29  ameyer
# Fixed bugs in new code.
#
# Revision 1.11  2002/04/25 15:54:09  ameyer
# Added formatAddress - Bob's formatter used in several mailers.
# Added getDocList - to return the list of doc ids plus version numbers.
#
# Revision 1.10  2002/02/14 20:21:18  ameyer
# Removed the block on printing.  Will add a new control for this soon.
#
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

import cdr, cdrdb, cdrxmllatex, os, re, sys, time, xml.dom.minidom, socket
import UnicodeToLatex, tarfile, zipfile, glob

debugCtr = 1

_LOGFILE = "d:/cdr/log/mailer.log"

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

        formatAddress(addr)
            Formats address information into a block of printable
            text lines and returns the block.

        createAddressLabelPage(addr, upperCase)
            Creates LaTeX for a sheet containing just an address label.
            If upperCase is true (which it is by default, the address
            strings are uppercased before being marked up for LaTeX.

        getCipsContactAddress(id)
            Returns an Address object for the ContactDetail information
            in a Person document identified as the CIPS contact address.

        getOrganizationAddress (id):
            Returns an Address object for the ContactDetail information
            in an Organization document.  Handles cases of directly
            referenced CIPSContactPerson, and generic Administrators.

        makeIndex()
            Builds an index list of recipients from the dictionary
            of Recipient objects and sorts it by country and
            postalCode.

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
    __CDR_EMAIL     = "cdr@%s.nci.nih.gov" % socket.gethostname()
    __SMTP_RELAY    = "MAILFWD.NIH.GOV"
    __LOGFILE       = _LOGFILE
    __DEF_PRINTER   = "\\\\CIPSFS1\\HP8100"
    __INCLUDE_PATH  = "d:/cdr/Mailers/include"
    __ERR_PATTERN   = re.compile("<Err>(.*)</Err>")
    __LATEX_OPTS    = "-halt-on-error -quiet -interaction batchmode "\
                      "-include-directory d:/cdr/mailers/style"

    #------------------------------------------------------------------
    # Constructor for base class.
    #------------------------------------------------------------------
    def __init__(self, jobId, batchPrinting = 1):
        """
        Parameters:
            jobId               - Integer for publication job number.
        """
        self.__id               = jobId
        self.__nMailers         = 0
        self.__docIds           = []
        self.__recipients       = {}
        self.__index            = []
        self.__documents        = {}
        self.__parms            = {}
        self.__printer          = MailerJob.__DEF_PRINTER
        self.__batchPrinting    = batchPrinting

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
    def getIndex     (self): return self.__index
    def getDocuments (self): return self.__documents
    def getMailerIncludePath(self): return self.__INCLUDE_PATH
    def printDirect  (self): self.__batchPrinting = 0
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
            self.log("~~Finished __loadSettings")
            self.__mailerCleanup()
            self.log("~~Finished __mailerCleanup")
            self.__createQueue()
            self.log("~~Finished __createQueue")
            self.fillQueue()
            self.__printQueue(self.__batchPrinting)
            self.__cleanup("Success", "Processed %d mailers" % self.__nMailers)
            self.log("******** finished mailer job ********")
            return 0
        except:
            (eType, eValue) = sys.exc_info()[:2]
            errMessage = eValue or eType
            self.log("ERROR: %s" % errMessage, tback=1)
            self.__cleanup("Failure", errMessage)
            return 1

    #------------------------------------------------------------------
    # Append message to logfile.
    #------------------------------------------------------------------
    def log(self, message, tback=None):
        """
        Appends progress or error information to a log file.  Each
        entry is stamped with the current date and time and the
        number of the current publication job.  No return value.
        No exceptions raised.
        """
        try:
            msg = "Job %d: %s" % (self.__id, message)
            cdr.logwrite (msg, MailerJob.__LOGFILE, tback)
            # now = time.ctime(time.time())
            # msg = "[%s] Job %d: %s" % (now, self.__id, message)
            # open(MailerJob.__LOGFILE, "a").write(msg + "\n")
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
        raise StandardError ("fillQueue() must be defined by derived class")

    #------------------------------------------------------------------
    # Generate a document for tracking a mailer.
    #------------------------------------------------------------------
    def addMailerTrackingDoc(self, doc, recipient, mailerType,
                             remailerFor = None):
        """
        Parameters:
            doc         - Object of type Document, defined below
            recipient   - Object of type Recipient, defined below
            mailerType  - String containing a values matching the
                          list of valid values for MailerType
                          enumerated in the schema for Mailer docs.
            remailerFor - optional integer for the document ID of
                          an earlier mailer that was sent out and
                          never responded to, and for which this
                          is a followup remailer.
        Return value:
            Integer ID for the newly inserted Mailer document.
        """

        if remailerFor:
            remailerFor = "\n  <RemailerFor cdr:ref='%s'/>" % \
                          cdr.normalize(remailerFor)
        else:
            remailerFor = ""
        recipId = "CDR%010d" % recipient.getId()
        docId   = "CDR%010d" % doc.getId()
        address = recipient.getAddress().getXml()
        xml     = u"""\
<CdrDoc Type="Mailer">
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr="cips.nci.nih.gov/cdr">
   <Type>%s</Type>%s
   <JobId>%d</JobId>
   <Recipient cdr:ref="%s">%s</Recipient>
   %s
   <Document cdr:ref="%s">%s</Document>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (docId, recipId, mailerType, remailerFor, self.__id, recipId,
       recipient.getName(), address, docId, doc.getTitle(),
       self.__now, self.__deadline)
        rsp   = cdr.addDoc(self.__session, doc = xml.encode('utf-8'), 
                           checkIn = "Y", ver = "Y", val = 'Y')
        match = self.__ERR_PATTERN.search(rsp)
        if match:
            err = match.group(1)
            raise StandardError (
                "failure adding tracking document for %s: %s" % (docId, err))
        self.__nMailers += 1
        digits = re.sub("[^\d]", "", rsp)
        return int(digits)

    #------------------------------------------------------------------
    # Convert Unicode string to Latin-1 character set.
    #------------------------------------------------------------------
    def encodeLatin1(self, unicodeString):
        return unicodeString.encode('latin-1')

    #------------------------------------------------------------------
    # Retrieve the CIPS contact Address for a mailer recipient.
    #------------------------------------------------------------------
    def getCipsContactAddress(self, id):
        """
        Parameters:
            id          - Integer ID for CDR Person document.
            docType     - 'Person' (default) or 'Organization'
        Return value:
            Returns an Address object for the CIPS contact.
        """
        # Make string version of id
        docId  = cdr.normalize(id)

        # Find fragment ID for CIPS contact location in Person doc
        rows = cdr.getQueryTermValueForId (
                '/Person/PersonLocations/CIPSContact', id, self.__conn)
        if not rows:
            raise StandardError("no CIPSContact for %s" % docId)
        fragId = rows[0]

        # Filter to create AddressElement XML
        filters = ["name:Person Address Fragment With Name"]
        result  = cdr.filterDoc(self.__session, filters, docId,
                                parm = (('fragId', fragId),))

        # Expecting tuple of xml fragment, messages.  Single string is error.
        if type(result) == type(""):
            raise StandardError ( \
                "failure extracting contact address for %s: %s" % ( docId,
                result))
        return Address(result[0])

    #------------------------------------------------------------------
    # Retrieve the CIPS contact Address object for an Organization
    #------------------------------------------------------------------
    def getOrganizationAddress (self, id):
        """
        Parameters:
            id - Integer ID of the organization document.
        Return value:
            Address object for organization.
        """
        # Default 'name' of the recipient
        nameStr = 'Administrator'

        # See if we have a CIPS contact person whose real name we can use
        rows = cdr.getQueryTermValueForId (
             '/Organization/OrganizationDetails/CIPSContactPerson/@cdr:ref',
             id, self.__conn)
        if rows:
            # Construct and Address object for person, to get real name
            # Fatal error if we can't find one
            personAddr = self.getCipsContactAddress (rows[0])
            nameStr = personAddr.getAddressee()

        # Find the fragment id in the Organization doc for
        #   the address we need to send to
        # Filter the organization to construct an address
        rows = cdr.getQueryTermValueForId (
             '/Organization/OrganizationLocations/CIPSContact',
             id, self.__conn)
        if not rows:
            raise StandardError (
                "No CIPSContact element found for Organization %d" % id)

        filters = ["name:Organization Address Fragment"]
        parms   = (("fragId", rows[0]),)
        result  = cdr.filterDoc(self.__session, filters, id, parm=parms)

        # Expecting tuple of xml fragment, messages.  Single string is error.
        if type(result) == type(""):
            raise StandardError ( \
                "failure extracting contact address for %d: %s" % (id, result))

        # Construct an address from returned XML
        orgAddr = Address(result[0])

        # Add or replace the name string with the one we constructed above
        orgAddr.setAddressee (nameStr)

        return orgAddr

    #------------------------------------------------------------------
    # Generate an index of the mailers in order of country + postal code.
    #------------------------------------------------------------------
    def makeIndex(self):
        self.__index   = []
        recipients     = self.getRecipients()
        for recipKey in recipients.keys():
            recip      = recipients[recipKey]
            address    = recip.getAddress()
            country    = address.getCountry()
            postalCode = address.getPostalCode()
            for doc in recip.getDocs():
                self.__index.append((country, postalCode, recip, doc))
        self.__index.sort()

    #------------------------------------------------------------------
    # Generate LaTeX source for a mailer document.
    #------------------------------------------------------------------
    def makeLatex(self, doc, filters, mailType = '', parms = None):
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

        parm = parms or []
        docId = cdr.normalize(doc.getId())
        result = cdr.filterDoc(self.__session, filters, docId, parm = parm,
                               docVer = doc.getVersion())
        if type(result) in (type(""), type(u"")):
            raise StandardError (\
                "failure filtering document %s: %s" % (docId, result))
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
            raise StandardError ( \
                "failure generating LaTeX for %s: %s" % (docId, eMsg))

    #------------------------------------------------------------------
    # Create a formatted address block from an Address object.
    #------------------------------------------------------------------
    def formatAddress(self, addr):
        return addr.format().getBlock()

    #------------------------------------------------------------------
    # Create LaTeX for a sheet containing just an address label.
    #------------------------------------------------------------------
    def createAddressLabelPage(self, addr, upperCase = 1):
        """
        Parameters:
            addr        - Object representing an address.
            upperCase   - Optional flag requesting that the address
                          strings be converted to uppercase.
        Notes:
            The window for the address labels is small, and the
            envelope is larger than the sheet, so we drop the
            country name line for U.S. addresses to save space.
        Return value:
            String containing LaTeX for address label sheet.
        """
        formattedAddress = addr.format(upperCase = upperCase, dropUS = 1,
                                       wrapAt = 63)
        return cdrxmllatex.createAddressLabelPage(formattedAddress)

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
            for unused in range(passCount):
                rc = os.system("latex %s %s" % (self.__LATEX_OPTS, filename))
                if rc:
                    raise StandardError ( \
                        "failure running LaTeX processor on %s" % filename)
            rc = os.system("dvips -q %s" % basename)
            if rc:
                raise StandardError ( \
                    "failure running dvips processor on %s.dvi" % basename)
            return PrintJob(basename + ".ps", jobType)

        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue or eType
            raise "failure converting %s.tex to %s.ps: %s" % (basename,
                                                              basename,
                                                              eMsg)

    #------------------------------------------------------------------
    # Clear out orphaned mailer tracking documents (from failed jobs).
    #------------------------------------------------------------------
    def __mailerCleanup(self):
        try:
            results = cdr.mailerCleanup(self.__session)
            if results[0]:
                self.log("%d tracking document(s) marked as deleted" %
                         len(results[0]))
            for err in results[1]:
                self.log(u"__mailerCleanup: %s" % err)
        except:
            self.log("mailerCleanup failure", 1)
        
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
    # Load the list of document IDs and other descriptive information
    # for each document to be mailed by this job.
    #------------------------------------------------------------------
    def __getPubProcDocRows(self):

        try:
            # Find id, version, title, document type name
            #   for each document previously selected for mailing
            self.__cursor.execute("""\
                SELECT pub.doc_id, pub.doc_version,
                       doc.title, type.name
                  FROM pub_proc_doc pub
                  JOIN document doc
                    ON pub.doc_id = doc.id
                  JOIN doc_type type
                    ON doc.doc_type = type.id
                 WHERE pub_proc = ?""", (self.__id,))
            docDescriptorList = self.__cursor.fetchall()

            # Can't continue if there aren't any
            if not docDescriptorList:
                raise "no documents found for job %d" % self.__id

            # Build a list of pure docIds (used by some software)
            #   and of fuller information
            for row in docDescriptorList:

                # Append the id to plain list of ids
                self.__docIds.append(row[0])

                # Create a document object and add it to list of objects
                self.__documents[row[0]] = \
                    Document (row[0], row[2], row[3], row[1])

            if not docDescriptorList:
                raise "no documents found for job %d" % self.__id

            # Convert the id list to a faster tuple
            # [Not sure why Bob did this]
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
    # Also creates and changes to the output directory.
    #------------------------------------------------------------------
    def __createQueue(self):
        self.__queue = []

        # Does the output directory already exist
        try:
            os.chdir(self.__outputDir)
        except:
            # Doesn't exist, try to create it
            try:
                os.makedirs(self.__outputDir)
            except:
                self.log ("Unable to create working directory", tback=1)
                raise "failure creating working directory %s" % \
                      self.__outputDir
            try:
                os.chdir(self.__outputDir)
            except:
                self.log ("Unable to change to working directory", tback=1)
                raise "failure setting working directory to %s" % \
                      self.__outputDir

    #------------------------------------------------------------------
    # Print the jobs in the queue.
    #------------------------------------------------------------------
    def __printQueue(self, batchPrint = 1):
        if batchPrint:
            PrintJob(0, PrintJob.DUMMY).writePrologFiles()
            outputFile = open("PrintJob.cmd", "w")
            outputFile.write("@if %1. ==. goto usage\n")
        else:
            outputFile = self.__printer
        for job in self.__queue:
            job.Print(outputFile, self.log, batchPrint)
        if batchPrint:
            outputFile.write("goto done\n")
            outputFile.write(":usage\n")
            outputFile.write("@echo usage: PrintJob path-to-printer\n")
            outputFile.write("@echo  e.g.: PrintJob \\\\CIPSFS1\\HP8100\n")
            outputFile.write(":done\n")
            outputFile.close()
            self.__packageFiles()

    #------------------------------------------------------------------
    # Create archive packages for the job's files.
    # Assumption: the current working directory is the job's output
    # output directory.  We switch to the parent of that directory.
    # This side effect should have no undesirable consequences,
    # because this is the last thing we do for the job.
    # Note: all files with the extensions '.xml', '.tex', '.log',
    # '.aux', and '.dvi' are packaged in a separate compressed tar
    # archive for intermediate files.  Everything else goes into a
    # second tar archive, used to print the actual mailer documents.  
    # Make sure nothing needed by this second archive gets a filename 
    # extension used for the intermediate file archive.
    #------------------------------------------------------------------
    def __packageFiles(self):
        self.log("~~In packageFiles")
        workExt   = ('xml', 'tex', 'log', 'aux', 'dvi')
        dir       = "Job%d" % self.getId()
        workName  = "SupportFilesForJob%d.tar" % self.getId()
        printName = "PrintFilesForJob%d.tar" % self.getId()
        os.chdir("..")
        if not os.path.isdir(dir):
            raise StandardError("INTERNAL ERROR: cannot find directory %s"
                    % dir)
        try:
            workFile = tarfile.TarFile(workName, 'w')
            for ext in workExt:
                for file in glob.glob('%s/*.%s' % (dir, ext)):
                    workFile.write(file)
            workFile.close()
            p = os.popen('bzip2 %s' % workName)
            output = p.read()
            if p.close():
                raise StandardError("failure packing working files for job: %s"
                                    % output)
            for ext in workExt:
                for file in glob.glob('%s/*.%s' % (dir, ext)):
                    os.unlink(file)
        except:
            raise StandardError("failure packing working files for job")

        try:
            printFile = tarfile.TarFile(printName, 'w')
            for file in os.listdir(dir):
                printFile.write("%s/%s" % (dir, file))
            printFile.close()
            p = os.popen('bzip2 %s' % printName)
            output = p.read()
            if p.close():
                raise StandardError("failure creating print job package: %s"
                                    % output)
            for file in os.listdir(dir):
                os.unlink("%s/%s" % (dir, file))
        except:
            raise StandardError("failure creating print job package")
        os.rmdir(dir)

    #------------------------------------------------------------------
    # Clean up.
    #------------------------------------------------------------------
    def __cleanup(self, status, message):
        self.log("~~In cleanup")
        try:
            self.__updateStatus(status, message)
            self.__sendMail()
            if self.__session: cdr.logout(self.__session)
        except:
            self.log ("__cleanup failed, status was '%s'" % status,
                      tback=1)

    #------------------------------------------------------------------
    # Update the pub_proc table's status.
    #------------------------------------------------------------------
    def __updateStatus(self, status, message = None):
        self.log("~~In update status, status=%s" % status)
        message = message and str(message)
        try:
            if message:
                self.log ("  (message: %s)" % message)
            self.__cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?,
                       messages = ?,
                       completed = GETDATE()
                 WHERE id = ?""", (status, message, self.__id))
            self.__conn.commit()
        except:
            self.log ("__updateStatus failed, status was '%s'" % status,
                      tback=1)

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

    http://%s.nci.nih.gov/cgi-bin/cdr/PubStatus.py?id=%d

Please do not reply to this message.
""" % (self.__id, socket.gethostname(), self.__id)
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

        PLAIN
            Used for non-PostScript which should not be stapled.

        DUMMY
            Used to make a dummy object for writing prolog PCL files.

        Print()
            Writes the current print job to the specified printer.
    """
    DUMMY            = 0
    MAINDOC          = 1
    COVERPAGE        = 2
    PLAIN            = 3
    __STAPLE_NAME    = "StapleProlog.pcl"
    __NONSTAPLE_NAME = "NonStapleProlog.pcl"
    __PLAIN_NAME     = "PlainProlog.pcl"
    __PAGES_PATTERN  = re.compile("%%Pages: (\\d+)")
    __MAX_STAPLED    = 25
    __STAPLE_PROLOG  = """\
\033%-12345X@PJL
@PJL SET FINISH=STAPLE
@PJL SET STAPLEOPTION=ONE
@PJL SET OUTBIN=OPTIONALOUTBIN2
@PJL ENTER LANGUAGE=POSTSCRIPT
"""
    __NONSTAPLE_PROLOG = """\
\033%-12345X@PJL
@PJL SET OUTBIN=OPTIONALOUTBIN2
@PJL ENTER LANGUAGE=POSTSCRIPT
"""
    __PLAIN_PROLOG = """\
\033%-12345X@PJL
@PJL SET OUTBIN=OPTIONALOUTBIN2
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
    # Create copies of the prolog PCL files in the job directory.
    #------------------------------------------------------------------
    def writePrologFiles(self):
        open(self.__STAPLE_NAME,    "w").write(self.__STAPLE_PROLOG)
        open(self.__NONSTAPLE_NAME, "w").write(self.__NONSTAPLE_PROLOG)
        open(self.__PLAIN_NAME,     "w").write(self.__PLAIN_PROLOG)

    #------------------------------------------------------------------
    # Send the current print job to the specified printer.
    # Have to use Print instead of print to avoid conflict with the
    # keyword.
    #------------------------------------------------------------------
    def Print(self, outFile, logFunc, batch = 1):
        logFunc("printing %s %s" % (
            self.__filename,
            self.__staple and "(stapled)" or ""))

        if batch:
            if self.__staple                  : prolog = self.__STAPLE_NAME
            elif self.__filetype != self.PLAIN: prolog = self.__NONSTAPLE_NAME
            else                              : prolog = self.__PLAIN_NAME
            outFile.write("copy %s+%s %%1\n" % (prolog, self.__filename))
        else:
            prn = open(outFile, "w")
            doc = open(self.__filename).read()
            if self.__staple:
                prn.write(self.__STAPLE_PROLOG + doc)
            elif self.__filetype != PrintJob.PLAIN:
                prn.write(self.__NONSTAPLE_PROLOG + doc)
            else:
                prn.write(self.__PLAIN_PROLOG + doc)
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

        getVersion()
            Returns the version number in the version archive of the
            document to be mailed.  If None, we are mailing the
            current working document.

    """
    def __init__(self, id, title, docType, version=None):
        self.__id         = id
        self.__title      = title
        self.__docType    = docType
        self.__version    = version
    def getId     (self): return self.__id
    def getTitle  (self): return self.__title
    def getDocType(self): return self.__docType
    def getVersion(self): return self.__version

#----------------------------------------------------------------------
# Object to hold a formatted address.
#----------------------------------------------------------------------
class FormattedAddress:
    def __init__(self, block, numLines):
        self.__block = block
        self.__numLines = numLines
    def getBlock(self):     return self.__block
    def getNumLines(self):  return self.__numLines

#----------------------------------------------------------------------
# Object to hold information about a mailer address.
#----------------------------------------------------------------------
class Address:
    """
    Public methods:

        format(upperCase, dropUS)
            Returns address in a format ready for inclusion in a
            LaTeX document.  If upperCase is true (default is false),
            then the address uses uppercase versions of the data
            for the formatted block.  If dropUS is true (default
            is false), the last line is omitted if it contains
            only the abbreviation for the United States.

        getNumAddressLines(dropUS)
            Returns the number of lines in the formatted address.
            The last line is not counted if dropUS is true and the
            last line contains only the abbreviation for the United
            States.

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
                             The top node should be <AddressElements>
        """
        self.__addressee     = None
        self.__orgs          = []   # Main + parent orgs in right order
        self.__street        = []
        self.__city          = None
        self.__citySuffix    = None
        self.__state         = None
        self.__country       = None
        self.__postalCode    = None
        self.__codePos       = None
        self.__addressLines  = None

        if type(xmlFragment) == type("") or type(xmlFragment) == type(u""):
            dom = xml.dom.minidom.parseString(xmlFragment)
        else:
            dom = xmlFragment

        # No organization name nodes identified yet
        orgParentNode = None

        # Parse parts of an address
        if dom:
            for node in dom.documentElement.childNodes:
                if node.nodeName == 'PostalAddress':
                    self.__parsePostalAddress(node)
                elif node.nodeName in ('Name', 'PersonName'):
                    self.__addressee = self.__buildName(node)
                elif node.nodeName == 'OrgName':
                    self.__orgs.append (cdr.getTextContent(node))
                elif node.nodeName == 'ParentNames':
                    orgParentNode = node

        # If we got them, get org parent names to __orgs in right order
        if orgParentNode:
            self.__parseOrgParents (orgParentNode)

    #------------------------------------------------------------------
    # Public access methods.
    #------------------------------------------------------------------
    def getNumStreetLines (self): return len(self.__street)
    def getNumOrgs        (self): return len(self.__orgs)
    def getStreetLine(self, idx): return self.__street[idx]
    def getOrg       (self, idx): return self.__orgs[idx]
    def getCity           (self): return self.__city
    def getCitySuffix     (self): return self.__citySuffix
    def getState          (self): return self.__state
    def getCountry        (self): return self.__country
    def getPostalCode     (self): return self.__postalCode
    def getCodePosition   (self): return self.__codePos
    def getAddressee      (self): return self.__addressee

    # Caller may need to manipulate the name line of the address
    def setAddressee (self, nameStr): self.__addressee = nameStr


    #------------------------------------------------------------------
    # Calculate the number of lines in a formatted address block.
    #------------------------------------------------------------------
    def getNumAddressLines(self, dropUS = 0):
        lines = self.__getAddressLines()
        if not lines: return 0
        if self.__lineIsUS(lines[-1]): return len(lines) - 1
        return len(lines)

    #------------------------------------------------------------------
    # Create a LaTeX-ready string representing this address.
    #------------------------------------------------------------------
    def format(self, upperCase = 0, dropUS = 0, wrapAt = sys.maxint):
        lines = self.__getAddressLines()
        if upperCase:
            upperLines = []
            for line in lines:
                upperLines.append(line.upper())
            lines = upperLines
        if dropUS and len(lines) and self.__lineIsUS(lines[-1]):
            lines = lines[:-1]
        lines = self.__wrapLines(lines, wrapAt)
        return self.__formatAddressFromLines(lines)

    #------------------------------------------------------------------
    # Create XML string from address information.
    #------------------------------------------------------------------
    def getXml(self):
        xml = "<MailerAddress>"
        if self.__country:
            xml += "<Country>%s</Country>" % self.__country
        if self.__postalCode:
            xml += "<PostalCode>%s</PostalCode>" % self.__postalCode
        for line in self.__getAddressLines():
            xml += "<AddressLine>%s</AddressLine>" % line
        return xml + "</MailerAddress>"

    #------------------------------------------------------------------
    # Perform word wrap if needed.
    #------------------------------------------------------------------
    def __wrapLines(self, lines, wrapAt):
        needWrap = 0
        for line in lines:
            if len(line) > wrapAt:
                needWrap = 1
                break
        if not needWrap:
            return lines
        newLines = []
        for line in lines:
            indent = 0
            while len(line) > wrapAt - indent:
                partLen = wrapAt - indent
                while partLen > 0:
                    if line[partLen] == ' ':
                        break
                    partLen -= 1
                if partLen == 0:
                    partLen = wrapAt - indent
                firstPart = line[:partLen].strip()
                line = line[partLen:].strip()
                if firstPart:
                    newLines.append(' ' * indent + firstPart)
                    indent = 2
            if line:
                newLines.append(' ' * indent + line)
        return newLines

    #------------------------------------------------------------------
    # Extract postal address element values.
    #------------------------------------------------------------------
    def __parsePostalAddress(self, node):
        """
        Extracts individual elements from street address, storing
        each in a field of the Address object.

        Pass:
            node    - DOM node of PostalAddress element
        """
        for child in node.childNodes:
            if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if child.nodeName == "Street":
                    self.__street.append(cdr.getTextContent(child))
                elif child.nodeName == "City":
                    self.__city = cdr.getTextContent(child)
                elif child.nodeName == "CitySuffix":
                    self.__citySuffix = cdr.getTextContent(child)
                    print "citySuffix: %s" % self.__citySuffix
                elif child.nodeName in ("State", "PoliticalSubUnit_State"):
                    self.__state = cdr.getTextContent(child)
                elif child.nodeName == "Country":
                    self.__country = cdr.getTextContent(child)
                elif child.nodeName == "PostalCode_ZIP":
                    self.__postalCode = cdr.getTextContent(child)
                elif child.nodeName == "CodePosition":
                    self.__codePos = cdr.getTextContent(child)

    #------------------------------------------------------------------
    # Extract and sort (if necessary) organization name values of parents
    #------------------------------------------------------------------
    def __parseOrgParents (self, node):
        """
        Parses a ParentNames element, extracting organization names
        and appending them, in the right order, to the list of
        organizations.

        Pass:
            node    - DOM node of ParentNames element
        """
        # Attribute tells us the order in which to place parents
        parentsFirst = 0
        pfAttr = node.getAttribute("OrderParentNameFirst")
        if pfAttr == "Yes":
            parentsFirst = 1

        for child in node.childNodes:
            if child.nodeName == "ParentName":
                self.__orgs.append(cdr.getTextContent(child))
        if parentsFirst:
            self.__orgs.reverse()

    #------------------------------------------------------------------
    # Construct name string from components.
    #------------------------------------------------------------------
    def __buildName(self, node):
        """
        Parameters:
            node - PersonName subelement DOM node from an
                   AddressElements node.
        Return value:
            String containing formatted name, e.g.:
                "Dr. John Q. Kildare, Jr."
        """
        givenName = ""
        surname   = ""
        prefix    = ""
        gSuffix   = ""
        mi        = ""
        pSuffixes = []
        for child in node.childNodes:
            if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if child.nodeName == "GivenName":
                    givenName = cdr.getTextContent(child)
                elif child.nodeName == "SurName":
                    surname = cdr.getTextContent(child)
                elif child.nodeName == "Prefix":
                    prefix = cdr.getTextContent(child)
                elif child.nodeName == "GenerationSuffix":
                    gSuffix = cdr.getTextContent(child)
                elif child.nodeName == "MiddleInitial":
                    mi = cdr.getTextContent(child)
                elif child.nodeName == "ProfessionalSuffix":
                    for grandchild in child.childNodes:
                        if grandchild.nodeName in (
                                         "StandardProfessionalSuffix",
                                         "CustomProfessionalSuffix"):
                            suffix = cdr.getTextContent(grandchild)
                            if suffix:
                                pSuffixes.append(suffix)

        name = ("%s %s" % (prefix, givenName)).strip()
        name = ("%s %s" % (name, mi)).strip()
        name = ("%s %s" % (name, surname)).strip()
        if gSuffix:
            name = "%s, %s" % (name, gSuffix)
        rest = ", ".join(pSuffixes).strip()
        if rest:
            name = "%s, %s" % (name, rest)
        return name

    #------------------------------------------------------------------
    # Format an address block from its address lines.
    #------------------------------------------------------------------
    def __formatAddressFromLines(self, lines):
        block = ""
        for line in lines:
            block += "%s \\\\\n" % UnicodeToLatex.convert(line)
        return FormattedAddress(block, len(lines))

    #------------------------------------------------------------------
    # Construct a list of strings representing the lines of a
    # formatted address.  This part of address formatting is broken
    # out separately, so we can cache the results, and so we can
    # hand out the lines without the formatting for routines like
    # the one which creates address label sheets (which use uppercase
    # versions of the address line strings).
    #------------------------------------------------------------------
    def __getAddressLines(self):
        if self.__addressLines is None:
            lines = []
            orgLines = []
            if self.getNumOrgs():
                for i in range(self.getNumOrgs()):
                    org = self.getOrg(i)
                    if org:
                        orgLines.append(self.getOrg(i))
            addressee = self.getAddressee()
            if addressee:
                lines.append(addressee)
            if orgLines:
                lines += orgLines
            for i in range(self.getNumStreetLines()):
                streetLine = self.getStreetLine(i)
                if streetLine:
                    lines.append(streetLine)
            city    = self.getCity()
            suffix  = self.getCitySuffix()
            state   = self.getState()
            zip     = self.getPostalCode()
            pos     = self.getCodePosition()
            country = self.getCountry()
            line    = ""
            city    = ("%s %s" % (city or "",
                                  suffix or "")).strip()
            print "city=%s; suffix=%s" % (str(city), str(suffix))
            if zip and pos == "before City":
                line = zip
                if city: line += " "
            if city: line += city
            if zip and pos == "after City":
                if line: line += " "
                line += zip
            if state:
                if line: line += ", "
                line += state
            if zip and (not pos or pos == "after PoliticalUnit_State"):
                if line: line += " "
                line += zip
            if line:
                lines.append(line)
            if country:
                if zip and pos == "after Country":
                    lines.append("%s %s" % (country, zip))
                else:
                    lines.append(country)
            elif zip and pos == "after Country":
                lines.append(zip)
            self.__addressLines = lines
        return self.__addressLines

    #------------------------------------------------------------------
    # Check to see if a line is just U.S. (or the equivalent).
    #------------------------------------------------------------------
    def __lineIsUS(self, line):
        return line.strip().upper() in ("US", "USA", "U.S.", "U.S.A.")
