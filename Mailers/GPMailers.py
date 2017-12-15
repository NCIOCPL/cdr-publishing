#----------------------------------------------------------------------
#
# Creates the following structure for a GP mailer job and sends it
# to the emailer server's database.
#
# GPMailers
#  GP
#   @id
#   PersonNameInformation
#    GivenName [optional, mapped from PersonNameInformation/GivenName]
#    MiddleInitial [optional, mapped from PersonNameInformation/MiddleInitial]
#    Surname [required, mapped from PersonNameInformation/SurName]
#    Suffix [optional, mapped from PersonNameInformation/GenerationSuffix]
#   Contact [mapped from PRACTICELOCATIONS UsedFor='GPMailer']
#    Institution [mapped from INSTITUTION]
#    Address [mapped from CADD elements]
#    Telephone [mapped from CPHN]
#    Fax [mapped from Fax]
#    Email [mapped from CEML]
#    Web [mapped from WebSite/@xref]
#   PublishInDirectory [mapped from PRACTICELOCATIONS UsedFor='GPMAILER'
#                       CEML/@Public]
#   PracticeLocations
#    PracticeLocation [mapped from PRACTICELOCATIONS UsedFor='GP']
#     Institution [mapped from INSTITUTION]
#     Address [mapped from CADD elements]
#     Telephone [mapped from CPHN]
#   ProfessionalType [optional, multiple, mapped from ProfessionalType]
#   Degree [optional, multiple, mapped from DEGREE]
#   GeneticsBoardCertification [optional, multiple, mapped from
#                               GeneticsProfessionalDetails/
#                                GeneticsSpecialtyInformation/
#                                 GeneticsBoardCertification]
#    GeneticsBoardName [required, mapped from GeneticsBoardName]
#    CertificationStatus [required, mapped from CertificationStatus]
#    YearEligible [optional, mapped from EligibilityYear]
#   InterdisciplinaryTeamMember [required Yes/No, mapped from
#                   GeneticsProfessionalDetails/InterdisciplinaryTeamMember]
#   GeneticsTeamServices [optional, multiple, mapped from TEAMSERVICES]
#   ProvidesServices [required Yes/No, mapped from
#                   GeneticsProfessionalDetails/ProvidesServices]
#   AcceptsCalls [Yes/No, mapped from
#                   GeneticsProfessionalDetails/AcceptsCalls]
#   ServiceLimitations [text, need mapping]
#                   GeneticsProfessionalDetails/ServiceLimitations]
#   FamilyCancerSyndrome [multiple, optional,
#                         mapped from FAMILYCANCERSYNDROME/SYNDROMENAME]
#   MemberOfGeneticsSociety [optional, multiple,
#                            mapped from MEMBERSHIP/INSTITUTION]
#
# BZIssue::5295 (JIRA::OCECDR-3596) - changed source of PublishInDirectory
# JIRA::OCECDR-4114 - Python upgrade
#
#----------------------------------------------------------------------
import cdr, cdrdb, sys, bz2, cdrmailer, cdrmailcommon
import requests
from lxml import etree

class LookupValues:
    def __init__(self):
        self.__doc = None
        self.values = {}
        url = "https://%s/cgi-bin/cdr/GetGPLookupValues.py" % cdr.APPC
        try:
            response = requests.get(url)
        except:
            raise Exception("can't open URL: %s" % url)

        self.__doc = response.content
        tree = etree.XML(self.__doc)
        if tree.tag != 'ValueSets':
            raise Exception("can't find lookup values")
        for vs in tree.findall('ValueSet'):
            self.values[vs.get('type')] = values = []
            for v in vs.findall('Value'):
                values.append(v.text)
    def __getattr__(self, name):
        if name == 'compressedDoc':
            return bz2.compress(self.__doc)
        elif name in self.values:
            return self.values[name]
        raise AttributeError("attribute '%s' not found" % name)

def yn(flag):
    return flag and u'Yes' or u'No'

#----------------------------------------------------------------------
# Derived class for mailers to genetics professionals.
#----------------------------------------------------------------------
class GPMailerJob(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    # Nothing to do here: this is a purely electronic mailer job.
    #------------------------------------------------------------------
    def fillQueue(self): pass

    #------------------------------------------------------------------
    # These are the only type of mailers we generate for this job.
    #------------------------------------------------------------------
    def createEmailers(self):

        # Get valid values used on the CGI emailer form
        lookupValues = LookupValues()

        # Create the separate emailer directory and move to it.
        self.initEmailers(False)

        # Build the set of electronic mailers.
        ops = ",".join(cdr.getEmailList("Developers Notification"))
        root = etree.Element('GPMailers',
                             JobId=unicode(self.getId()),
                             JobTime=self.getJobTime(),
                             Ops=ops)
        self.getCursor().execute("""\
            SELECT d.doc_id, d.doc_version
              FROM pub_proc_doc d
              JOIN pub_proc p
                ON p.id = d.pub_proc
             WHERE p.id = ?""", self.getId())
        rows = self.getCursor().fetchall()
        self.log("%d rows retrieved for electronic mailers" % len(rows))
        for docId, docVer in rows:
            try:
                gp = GP(self.getCursor(), docId, docVer)
                address = (u"<MailerAddress><Email>%s"
                           "</Email></MailerAddress>" % gp.contact.email)
                trackerId = cdrmailcommon.recordMailer(self.getSession(),
                                                       docId, docId,
                                                       'Web-based',
                                                       self.getSubset(),
                                                       self.getJobTime(),
                                                       address,
                                                       jobId=self.getId(),
                                                       recipName=gp.fullName,
                                                       docTitle=gp.docTitle)
                root.append(gp.toElement(trackerId, lookupValues))
                self.log("processed CDR%d" % docId)
                self.bumpCount()
            except Exception, e:
                msg = "Failure processing CDR%d: %s" % (docId, e)
                sys.stderr.write("%s\n" % msg)
                self.log(msg, tback=True)
        mailers = etree.tostring(root)
        compressedDoc = bz2.compress(mailers)
        compressedLookupValues = lookupValues.compressedDoc
        emConn = cdrmailcommon.emailerConn('dropbox')
        emCursor = emConn.cursor()
        emCursor.execute("""\
            INSERT INTO gp_emailer_job (id, emailers, uploaded, mailer_type,
                                        lookup_values)
                VALUES (%s, %s, NOW(), %s, %s)""", (self.getId(),
                                                    compressedDoc,
                                                    self.getSubset(),
                                                    compressedLookupValues))
        emConn.commit()
        fp = open("GPMailers-%d.xml.bz2" % self.getId(), "wb")
        fp.write(compressedDoc)
        fp.close()
        fp = open("LookupValues-%d.xml.bz2" % self.getId(), "wb")
        fp.write(compressedLookupValues)
        fp.close()

        # For ease of debugging; remove for production.
        fp = open("d:/tmp/GPMailers-%d.xml" % self.getId(), "wb")
        fp.write(mailers)
        fp.close()

        self.log("%d emailers successfully generated" % self.getCount())

class GP:
    filterSet = ['set:Mailer GeneticsProfessional Set']
    class Name:
        def __init__(self, tree):
            self.first = self.middle = self.last = self.suffix = u''
            for p in tree.findall('PersonNameInformation'):
                for child in p:
                    if child.tag == 'GivenName':
                        self.first = child.text
                    elif child.tag == 'MiddleInitial':
                        self.middle = child.text
                    elif child.tag == 'SurName':
                        self.last = child.text
                    elif child.tag == 'GenerationSuffix':
                        self.suffix = child.text
        def toElement(self):
            e = etree.Element('PersonNameInformation')
            if self.first:
                etree.SubElement(e, 'GivenName').text = self.first
            if self.middle:
                etree.SubElement(e, 'MiddleInitial').text = self.middle
            if self.last:
                etree.SubElement(e, 'Surname').text = self.last
            if self.suffix:
                etree.SubElement(e, 'Suffix').text = self.suffix
            return e
        def getFullName(self):
            first = ("%s %s" % (self.first, self.middle)).strip()
            full = ("%s %s" % (first, self.last)).strip()
            if self.suffix:
                full += ", %s" % self.suffix
            return full
    class Location:
        def __init__(self, node):
            self.usedFor = (node.get('UsedFor') or '').split()
            self.inst = self.phone = self.fax = self.email = self.web = u''
            self.address = []
            self.publicEmail = None
            for child in node:
                if child.tag == 'INSTITUTION':
                    self.inst = child.text
                elif child.tag == 'CADD':
                    self.address.append(child.text)
                elif child.tag == 'CPHN':
                    self.phone = child.text
                elif child.tag == 'Fax':
                    self.fax = child.text
                elif child.tag == 'CEML':
                    self.email = child.text
                    self.publicEmail = child.get("Public") != "No"
                elif child.tag == 'WebSite':
                    self.web = child.get('xref') or u''
        def toElement(self, isContact = False):
            e = etree.Element(isContact and 'Contact' or 'PracticeLocation')
            if self.inst:
                etree.SubElement(e, 'Institution').text = self.inst
            if self.address:
                etree.SubElement(e, 'Address').text = u'\n'.join(self.address)
            if self.phone:
                etree.SubElement(e, 'Telephone').text = self.phone
            if isContact:
                if self.fax:
                    etree.SubElement(e, 'Fax').text = self.fax
                if self.email:
                    etree.SubElement(e, 'Email').text = self.email
                if self.web:
                    etree.SubElement(e, 'Web').text = self.web
            return e
    class Specialty:
        def __init__(self, node):
            self.name = self.status = u''
            self.yearEligible = None
            for child in node:
                if child.tag == 'GeneticsBoardName':
                    self.name = child.text
                elif child.tag == 'CertificationStatus':
                    self.status = child.text
                elif child.tag == 'EligibilityYear':
                    self.yearEligible = child.text
        def toElement(self):
            e = etree.Element('GeneticsBoardCertification')
            if self.name:
                etree.SubElement(e, 'GeneticsBoardName').text = self.name
            if self.status:
                etree.SubElement(e, 'CertificationStatus').text = self.status
            if self.yearEligible:
                etree.SubElement(e, 'YearEligible').text = self.yearEligible
            return e
    def __init__(self, cursor, docId, docVer):
        self.docId = docId
        response = cdr.filterDoc('guest', GP.filterSet, docId)
        if type(response) in (str, unicode):
            raise cdr.Exception(response)
        filterTree = etree.XML(response[0])
        cursor.execute("""\
            SELECT xml, title
              FROM doc_version
             WHERE id = ?
               AND num = ?""", (docId, docVer))
        rows = cursor.fetchall()
        if not rows:
            raise cdr.Exception("unable to retrieve CDR%s" % docId)
        cdrTree = etree.XML(rows[0][0].encode('utf-8'))
        self.name = GP.Name(cdrTree)
        self.fullName = self.name.getFullName()
        self.docTitle = rows[0][1]
        self.contact = None
        self.degrees = []
        self.locations = []
        self.professionalTypes = set()
        self.specialties = {}
        self.services = set()
        self.syndromes = set()
        self.societies = set()
        self.teamMember = self.publish = self.providesServices = False
        self.acceptsCalls = False
        self.limitations = None

        for details in cdrTree.findall('ProfessionalInformation'
                                       '/GeneticsProfessionalDetails'):
            for child in details:
                if child.tag == 'AcceptsCalls' and child.text == 'Yes':
                    self.acceptsCalls = True
                if child.tag == 'ProvidesServices' and child.text == 'Yes':
                    self.providesServices = True
                if (child.tag == 'InterdisciplinaryTeamMember' and
                    child.text == 'Yes'):
                    self.teamMember = True
                if child.tag == 'ServiceLimitations':
                    self.limitations = child.text
                if child.tag == 'GeneticsSpecialtyInformation':
                    for c in child.findall('GeneticsBoardCertification'):
                        specialty = GP.Specialty(c)
                        self.specialties[specialty.name] = specialty
        for e in filterTree.findall('PRACTICELOCATIONS'):
            location = GP.Location(e)
            if 'GP' in location.usedFor:
                self.locations.append(location)
            if 'GPMailer' in location.usedFor:
                self.contact = location
                if location.publicEmail:
                    self.publish = True
        for e in cdrTree.findall('ProfessionalType'):
            self.professionalTypes.add(e.text)
        for e in filterTree.findall('DEGREE'):
            self.degrees.append(e.text)
        for e in filterTree.findall('TEAMSERVICES'):
            self.services.add(e.text)
        for e in filterTree.findall('GENETICSERVICES/FAMILYCANCERSYNDROME'
                                    '/SYNDROMENAME'):
            self.syndromes.add(e.text)
        for e in filterTree.findall('MEMBERSHIP/INSTITUTION'):
            self.societies.add(e.text)
    def toElement(self, trackerId, lookupValues):
        e = etree.Element('GP', id=`self.docId`, tracker=`trackerId`)
        etree.SubElement(e, 'FullName').text = self.fullName
        e.append(self.name.toElement())
        if self.contact:
            e.append(self.contact.toElement(True))
        etree.SubElement(e, 'PublishInDirectory').text = yn(self.publish)
        if self.locations:
            locations = etree.SubElement(e, 'PracticeLocations')
            for location in self.locations:
                locations.append(location.toElement())
        for professionalType in lookupValues.ProfessionalTypes:
            if professionalType in self.professionalTypes:
                etree.SubElement(e, 'ProfessionalType').text = professionalType
        for degree in self.degrees:
            etree.SubElement(e, 'Degree').text = degree
        for specialty in lookupValues.Specialties:
            if specialty in self.specialties:
                e.append(self.specialties[specialty].toElement())
        ename = 'InterdisciplinaryTeamMember'
        etree.SubElement(e, ename).text = yn(self.teamMember)
        for service in lookupValues.TeamServices:
            if service in self.services:
                etree.SubElement(e, 'GeneticsTeamServices').text = service
        etree.SubElement(e, 'ProvidesServices').text = yn(self.providesServices)
        etree.SubElement(e, 'AcceptsCalls').text = yn(self.acceptsCalls)
        if self.limitations:
            etree.SubElement(e, 'ServiceLimitations').text = self.limitations
        for syndrome in lookupValues.Syndromes:
            if syndrome in self.syndromes:
                etree.SubElement(e, 'FamilyCancerSyndrome').text = syndrome
        for society in lookupValues.Societies:
            if society in self.societies:
                etree.SubElement(e, 'MemberOfGeneticsSociety').text = society
        return e

if __name__ == "__main__":
    sys.exit(GPMailerJob(int(sys.argv[1])).run())
