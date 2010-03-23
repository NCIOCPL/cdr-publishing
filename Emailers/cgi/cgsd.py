#!/usr/bin/python

#----------------------------------------------------------------------
#
# $Id$
#
# Genetics Professional electronic mailer interface.
#
# BZIssue::4630
#
#----------------------------------------------------------------------
import cgi, lxml.etree as etree, bz2, urllib2, re, util

def yn(flag): return flag and u'Yes' or u'No'

class GP:
    @staticmethod
    def getBoolean(b):
        if b is None:
            return None
        if type(b) not in (str, unicode):
            try:
                b = b.text
            except:
                return None
        if b == 'Yes':
            return True
        if b == 'No':
            return False
        return None
    @staticmethod
    def getFormValues(valueSet, fields, prefix):
        for i in range(int(fields.get('%s-max' % prefix))):
            value = fields.get('%s-%d' % (prefix, i + 1))
            if value:
                valueSet.add(value)
    def __init__(self, trackerId=None, personId=None, fields=None):
        self.trackerId = trackerId
        self.personId = personId
        self.name = self.contact = self.publish = self.teamMember = None
        self.providesServices = self.acceptsCalls = self.limitations = None
        self.completed = self.bounced = None
        self.degrees = []
        self.locations = []
        self.professionalTypes = set()
        self.specialties = {}
        self.services = set()
        self.syndromes = set()
        self.societies = set()
        if fields is not None:
            fields = util.wrapFieldsInMap(fields)
            self.trackerId = int(fields.get('tid'))
            self.personId = int(fields.get('pid'))
            self.job = int(fields.get('jid'))
            self.name = GP.Name(fields=fields)
            self.contact = GP.Location(fields=fields)
            self.publish = GP.getBoolean(fields.get('epub'))
            self.teamMember = GP.getBoolean(fields.get('idt'))
            self.providesServices = GP.getBoolean(fields.get('provsvc'))
            self.acceptsCalls = GP.getBoolean(fields.get('acpt'))
            self.limitations = fields.get('limits')
            self.degrees = fields.get('degrees', '').split(', ')
            for i in range(int(fields.get('loc-max'))):
                loc = GP.Location(fields=fields, pos=i + 1)
                if loc:
                    self.locations.append(loc)
            GP.getFormValues(self.professionalTypes, fields, 'pt')
            for i in range(int(fields.get('spec-max'))):
                specialty = GP.Specialty(fields=fields, pos=i + 1)
                if specialty:
                    self.specialties[specialty.board] = specialty
            GP.getFormValues(self.services, fields, 'ts')
            GP.getFormValues(self.syndromes, fields, 'syn')
            GP.getFormValues(self.societies, fields, 'memb')
        else:
            conn = util.getConnection('emailers')
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT xml, email, name, mailed, job, completed, bounced
                  FROM gp_emailer
                 WHERE id = %s
                   AND cdr_id = %s""", (trackerId, personId))
            rows = cursor.fetchall()
            if not rows:
                raise Exception("unable to find mailer document")
            (docXml, self.email, self.fullName, self.mailed, self.job,
             self.completed, self.bounced) = rows[0]
            tree = etree.XML(docXml)
            for child in tree:
                if child.tag == 'PersonNameInformation':
                    self.name = GP.Name(child)
                elif child.tag == 'Contact':
                    self.contact = GP.Location(child)
                elif child.tag == 'PublishInDirectory':
                    self.publish = GP.getBoolean(child)
                elif child.tag == 'PracticeLocations':
                    for location in child.findall('PracticeLocation'):
                        self.locations.append(GP.Location(location))
                elif child.tag == 'ProfessionalType':
                    self.professionalTypes.add(child.text)
                elif child.tag == 'Degree':
                    self.degrees.append(child.text)
                elif child.tag == 'GeneticsBoardCertification':
                    specialty = GP.Specialty(child)
                    self.specialties[specialty.board] = specialty
                elif child.tag == 'InterdisciplinaryTeamMember':
                    self.teamMember = GP.getBoolean(child)
                elif child.tag == 'GeneticsTeamServices':
                    self.services.add(child.text)
                elif child.tag == 'ProvidesServices':
                    self.providesServices = GP.getBoolean(child)
                elif child.tag == 'AcceptsCalls':
                    self.acceptsCalls = GP.getBoolean(child)
                elif child.tag == 'MemberOfGeneticsSociety':
                    self.societies.add(child.text)
                elif child.tag == 'FamilyCancerSyndrome':
                    self.syndromes.add(child.text)
                elif child.tag == 'ServiceLimitations':
                    self.limitations = child.text
        self.lookupValues = GP.LookupValues(self.job)
    def toElement(self):
        root = etree.Element('GP', id=`self.personId`,
                             tracker=`self.trackerId`)
        etree.SubElement(root, 'FullName').text = self.name.getFullName()
        root.append(self.name.toElement())
        root.append(self.contact.toElement(True))
        etree.SubElement(root, 'PublishInDirectory').text = yn(self.publish)
        if self.locations:
            locations = etree.SubElement(root, 'PracticeLocations')
            for location in self.locations:
                locations.append(location.toElement(False))
        for pt in self.lookupValues.ProfessionalTypes:
            if pt in self.professionalTypes:
                etree.SubElement(root, 'ProfessionalType').text = pt
        for degree in self.degrees:
            etree.SubElement(root, 'Degree').text = degree
        for specialty in self.lookupValues.Specialties:
            if specialty in self.specialties:
                root.append(self.specialties[specialty].toElement())
        ename = 'InterdisciplinaryTeamMember'
        etree.SubElement(root, ename).text = yn(self.teamMember)
        for service in self.lookupValues.TeamServices:
            if service in self.services:
                etree.SubElement(root, 'GeneticsTeamServices').text = service
        etree.SubElement(root,
                         'ProvidesServices').text = yn(self.providesServices)
        etree.SubElement(root, 'AcceptsCalls').text = yn(self.acceptsCalls)
        if self.limitations:
            etree.SubElement(root,
                             'ServiceLimitations').text = self.limitations
        for syndrome in self.lookupValues.Syndromes:
            if syndrome in self.syndromes:
                etree.SubElement(root, 'FamilyCancerSyndrome').text = syndrome
        for society in self.lookupValues.Societies:
            if society in self.societies:
                etree.SubElement(root,
                                 'MemberOfGeneticsSociety').text = society
        return root
    class Name:
        def __init__(self, node=None, fields=None):
            self.first = self.last = self.middle = self.suffix = None
            if fields is not None:
                self.first = fields.get('fname')
                self.last = fields.get('lname')
                self.middle = fields.get('mi')
                self.suffix = fields.get('suffix')
            else:
                for child in node:
                    if child.tag == 'GivenName':
                        self.first = child.text
                    elif child.tag == 'MiddleInitial':
                        self.middle = child.text
                    elif child.tag == 'Surname':
                        self.last = child.text
                    elif child.tag == 'Suffix':
                        self.suffix = child.text
        def getFullName(self):
            first = ("%s %s" % (self.first or u"", self.middle or u"")).strip()
            full = ("%s %s" % (first, self.last or u"")).strip()
            if self.suffix:
                full += ", %s" % self.suffix
            return full
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
                    
    class Location:
        def __init__(self, node=None, fields=None, pos=None):
            self.institution = self.address = self.phone = self.fax = None
            self.email = self.web = None
            if fields is not None:
                if pos is None:
                    self.institution = fields.get('inst')
                    self.address = fields.get('addr')
                    self.phone = fields.get('phone')
                    self.fax = fields.get('fax')
                    self.email = fields.get('email')
                    self.web = fields.get('weburl')
                else:
                    self.institution = fields.get('inst-%d' % pos)
                    self.address = fields.get('addr-%d' % pos)
                    self.phone = fields.get('phone-%d' % pos)
            else:
                for child in node:
                    if child.tag == 'Institution':
                        self.institution = child.text
                    elif child.tag == 'Address':
                        self.address = child.text
                    elif child.tag == 'Telephone':
                        self.phone = child.text
                    elif child.tag == 'Fax':
                        self.fax = child.text
                    elif child.tag == 'Email':
                        self.email = child.text
                    elif child.tag == 'Web':
                        self.web = child.text
            if self.address:
                self.address = self.address.replace("\r", "")
        def __nonzero__(self):
            if self.institution or self.address or self.phone: return True
            return False
        def toElement(self, isContact = False):
            e = etree.Element(isContact and 'Contact' or 'PracticeLocation')
            if self.institution:
                etree.SubElement(e, 'Institution').text = self.institution
            if self.address:
                etree.SubElement(e, 'Address').text = self.address
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
        def __init__(self, node=None, fields=None, pos=None):
            self.board = self.status = self.yearEligible = None
            if fields is not None:
                self.board = fields.get('bscb-%d' % pos)
                if fields.get('bccb-%d' % pos):
                    self.status = 'Certified'
                elif fields.get('becb-%d' % pos):
                    self.status = 'Eligible'
                else:
                    self.status = 'Not certified or eligible'
                self.yearEligible = fields.get('bycb-%d' % pos)
            else:
                for child in node:
                    if child.tag == 'GeneticsBoardName':
                        self.board = child.text
                    elif child.tag == 'CertificationStatus':
                        self.status = child.text
                    elif child.tag == 'YearEligible':
                        self.yearEligible = child.text
        def __nonzero__(self):
            return self.board and True or False
        def toElement(self):
            e = etree.Element('GeneticsBoardCertification')
            if self.board:
                etree.SubElement(e, 'GeneticsBoardName').text = self.board
            if self.status:
                etree.SubElement(e, 'CertificationStatus').text = self.status
            if self.yearEligible:
                etree.SubElement(e, 'YearEligible').text = self.yearEligible
            return e
    class LookupValues:
        def __init__(self, jobId):
            self.values = {}
            conn = util.getConnection('dropbox')
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT lookup_values
                  FROM dropbox.gp_emailer_job
                 WHERE id = %s""", jobId)
            rows = cursor.fetchall()
            if not rows:
                raise Exception("unable to load lookup values")
            tree = etree.XML(bz2.decompress(rows[0][0]))
            for vs in tree.findall('ValueSet'):
                self.values[vs.get('type')] = values = []
                for v in vs.findall('Value'):
                    values.append(v.text)
        def __getattr__(self, name):
            if name in self.values:
                return self.values[name]
            raise AttributeError("attribute '%s' not found" % name)

def clean(me):
    "Prepare value for '-delimited attribute"
    if me is None:
        return u""
    return cgi.escape(me).replace("'", "&#x27")

def showForm(fields):
    cdrId = fields.getvalue('person-id')
    trackerId = fields.getvalue('tracker-id')
    mailerId = fields.getvalue('id')
    if mailerId:
        mailerId = int(mailerId, 36)
        cdrId = mailerId & 0xFFFFFFFF
        trackerId = mailerId >> 32
    #lookupValues = LookupValues()
    gp = GP(trackerId, cdrId)
    if gp.completed:
        bail("The review of this set of information has already been "
             "completed.")
        return
    elif gp.bounced:
        bail("This mailer has been marked as 'Return To Sender'")
        return
    form = [u"""\
   <form action='cgsd.py' method='POST'>
    <input type='hidden' name='tid' value='%d' />
    <input type='hidden' name='pid' value='%d' />
    <input type='hidden' name='jid' value='%d' />
    <h1>Introduction</h1>
    <p class='instructions'>
     You are listed as a provider of genetics services in the
     <span class='name'><a href='http://www.cancer.gov/search/geneticsservices/'
     >NCI Cancer Genetics Services Directory</a></span>
     as part of the National Cancer Institute's
     <a href='http://www.cancer.gov'>Web site</a>.  Below is an
     electronic form that shows the information about you and your
     services currently listed in the <span class='name'>Directory</span>.
     Please review the information and update it by typing any changes
     directly into the boxes.
    </p>
    <p class='instructions'>
     If you have any questions, please call the PDQ Directory Desk
     at (301) 402-6722 or send e-mail to
     <a href='mailto:GeneticsDirectory@cancer.gov'
     >GeneticsDirectory@cancer.gov</a>.
    </p>
    <h1>1. Contact Information</h1>
    <p class='instructions'>
     Please verify all contact information.  This address is used
     to contact you for data verification purposes.
     It may be the same as one of the practice locations listed in the 
     <a href='http://www.cancer.gov/search/geneticsservices/'
     >online directory</a> (see <span class='name'><a href='#plocs'>Practice
     Locations</a></span> immediately below).
    </p>
    <br />
    <label class='label' for='lname'>Last Name:</label>
    <input class='field' name='lname' id='lname' value='%s' />
    <label class='label' for='fname'>First Name:</label>
    <input class='field' name='fname' id='fname' value='%s' />
    <label class='label' for='mi'>Middle Initial(s):</label>
    <input class='field' name='mi' id='mi' value='%s' />
    <label class='label' for='suffix'>Suffix:</label>
    <input class='field' name='suffix' id='suffix' value='%s' />
    <label class='label' for='inst'>Institution:</label>
    <input class='field' name='inst' id='inst' value='%s' />
    <label class='label' for='addr'>Contact Address:</label>
    <textarea name='addr' class='field' id='addr'>%s</textarea>
    <label class='label' for='phone'>Telephone:</label>
    <input class='field' name='phone' id='phone' value='%s' />
    <label class='label' for='fax'>Fax:</label>
    <input class='field' name='fax' id='fax' value='%s' />
    <label class='label' for='email'>E-mail:</label>
    <input class='field' name='email' id='email' value='%s' />
    <label class='label' for='epub'>Publish email address in directory?</label>
    <select name='epub' id='epub' class='field'>
     <option%s>Yes</option>
     <option%s>No</option>
    </select>
    <label class='label' for='weburl'>Web Address:</label>
    <input class='field' name='weburl' id='weburl' value='%s' />
<!--
    <label class='label' for='cmeth'>Preferred contact method:</label>
    <select name='cmeth' id='cmeth' class='field'>
     <option selected='selected'>E-Mail</option>
     <option>Mail</option>
    </select>
-->
    <h1><a name='plocs'></a>2. Practice Locations</h1>
    <input type='hidden' name='loc-max' value='%d' />
    <p class='instructions'>
     Please verify the practice location(s) for consultations and patient
     referrals, and list additional locations (up to a maximum of four
     total locations).
    </p>
    <br />
""" % (gp.trackerId, gp.personId, gp.job,
       gp.name and clean(gp.name.last) or u"",
       gp.name and clean(gp.name.first) or u"",
       gp.name and clean(gp.name.middle) or u"",
       gp.name and clean(gp.name.suffix) or u"",
       gp.contact and clean(gp.contact.institution) or u"",
       gp.contact and clean(gp.contact.address) or u"",
       gp.contact and clean(gp.contact.phone) or u"",
       gp.contact and clean(gp.contact.fax) or u"",
       gp.contact and clean(gp.contact.email) or u"",
       gp.publish == True and u" selected='selected'" or "",
       gp.publish == False and u" selected='selected'" or "",
       gp.contact and clean(gp.contact.web) or u"",
       max(len(gp.locations), 4))]
    locNum = 1
    for loc in gp.locations:
        form.append(u"""\
    <h2>Location %d</h2>
    <label class='label' for='inst-%d'>Institution:</label>
    <input class='field' name='inst-%d' id='inst-%d' value='%s' />
    <label class='label' for='addr-%d'>Contact Address:</label>
    <textarea name='addr-%d' class='field' id='addr-%d'>%s</textarea>
    <label class='label' for='phone-%d'>Telephone:</label>
    <input class='field' name='phone-%d' id='phone-%d' value='%s' />
""" % (locNum,
       locNum, locNum, locNum, clean(loc.institution),
       locNum, locNum, locNum, clean(loc.address),
       locNum, locNum, locNum, clean(loc.phone)))
        locNum += 1
    while locNum <= 4:
        form.append(u"""\
    <h2>Location %d</h2>
    <label class='label' for='inst-%d'>Institution:</label>
    <input class='field' name='inst-%d' id='inst-%d' value='' />
    <label class='label' for='addr-%d'>Contact Address:</label>
    <textarea name='addr-%d' class='field' id='addr-%d'></textarea>
    <label class='label' for='phone-%d'>Telephone:</label>
    <input class='field' name='phone-%d' id='phone-%d' value='' />
""" % (locNum,
       locNum, locNum, locNum,
       locNum, locNum, locNum,
       locNum, locNum, locNum))
        locNum += 1

    form.append(u"""\
    <h1>3. Type of Health Care Professional</h1>
    <p class='instructions'>
     Please verify information on type of health care
     professional (check all that apply).
    </p>
    <br />
    <input type='hidden' name='pt-max' value='%d' />
""" % len(gp.lookupValues.ProfessionalTypes))
    i = 1
    for value in gp.lookupValues.ProfessionalTypes:
        checked = value in gp.professionalTypes and " checked='checked'" or ""
        form.append(u"""\
    <input type='checkbox' class='indentedcb' name='pt-%d' id='pt-%d'%s
           value='%s' /> %s <br />
""" % (i, i, checked, clean(value), cgi.escape(value)))
        i += 1

    form.append(u"""\
    <h1>4. Degree(s)</h1>
    <p class='instructions'>
     Please verify academic degrees.
    </p>
    <!-- <label class='label' for='degrees'>Degrees:</label> -->
    <input class='field' name='degrees' id='degrees' value='%s' />

    <h1>5. Specialties and Certifications</h1>
    <p class='instructions'>
     Please verify genetics and oncology specialties and board
     certifications.
    </p>
    <br />
    <input type='hidden' name='spec-max' value='%d' />
    <table border='1' cellpadding='2' cellspacing='0'>
     <tr>                                                          
      <th>Specialty</th>
      <th>Board Certified</th>
      <th>Board Eligible</th>
      <th>Year Eligible</th>
     </tr>
""" % (u", ".join(gp.degrees), len(gp.lookupValues.Specialties)))
    i = 1
    for boardName in gp.lookupValues.Specialties:
        checked = certified = eligible = year = u""
        if boardName in gp.specialties:
            checked = " checked='checked'"
            specialty = gp.specialties[boardName]
            if specialty.status == 'Eligible':
                eligible = " checked='checked'"
            elif specialty.status == 'Certified':
                certified = " checked='checked'"
            year = specialty.yearEligible or u""
        form.append(u"""\
     <tr>
      <td>
       <input type='checkbox' id='bscb-%d' name='bscb-%d'%s value='%s' />
       %s
      </td>
      <td align='center'>
       <input type='checkbox' id='bccb-%d' name='bccb-%d'%s />
      </td>
      <td align='center'>
       <input type='checkbox' id='becb-%d' name='becb-%d'%s />
      </td>
      <td align='center'>
       <input class='year' maxlength='4' id='bycb-%d' name='bycb-%d'
              size='3' value='%s'/>
      </td>
     </tr>
""" % (i, i, checked, clean(boardName), cgi.escape(boardName),
       i, i, certified,
       i, i, eligible,
       i, i, year))
        i += 1

    form.append(u"""\
    </table>

    <h1>6. Team Services</h1>
    <p class='instructions'>
     Are you a member of an interdisciplinary team?
    </p>
    <input type='radio' name='idt' value='Yes'%s /> Yes<br />
    <input type='radio' name='idt' value='No'%s /> No<br />

    <p class='instructions'>
     If so, please verify the services provided by you or members of your
     team (check all that apply).
    </p>
    <input type='hidden' name='ts-max' value='%d' />
    <table border='0'>
""" % (gp.teamMember == True and " checked='checked'" or "",
       gp.teamMember == False and " checked='checked'" or "",
       len(gp.lookupValues.TeamServices)))

    i = 1
    for service in gp.lookupValues.TeamServices:
        form.append(u"""\
     <tr>
      <td valign='top'>
       <input type='checkbox' name='ts-%d' id='ts-%d'%s value='%s' />
      </td>
      <td>%s</td>
     </tr>
""" % (i, i, service in gp.services and " checked='checked'" or "",
       clean(service), cgi.escape(service)))
        i += 1

    form.append(u"""\
    </table>

    <h1>7. Professional Services</h1>
    <p class='instructions'>
     Do you currently provide professional services?
    </p>
    <input type='radio' name='provsvc' value='Yes'%s /> Yes<br />
    <input type='radio' name='provsvc' value='No'%s /> No<br />
    <p class='instructions'>
     Are you willing to accept calls or e-mails from
     individuals seeking familial cancer risk counseling
     and/or genetic susceptibility testing?
    </p>
    <input type='radio' name='acpt' value='Yes'%s /> Yes<br />
    <input type='radio' name='acpt' value='No'%s /> No<br />
    <p class='instructions'>
     Please indicate if there are restrictions to services
     provided (e.g., a person must be eligible for a clinical
     trial in order to receive services).
    </p>
    <input type='radio' name='rstrct' value='Yes'%s' /> 
    Yes (Please specify)<br />
    <textarea id='limits' name='limits'>%s</textarea><br />
    <input type='radio' name='rstrct' value='No'%s /> No<br />

    <h1>8. Predisposing Syndromes</h1>
    <p class='instructions'>
     Please verify the familial cancer predisposing syndromes for which
     you provide services.  A list of cancer sites and types associated
     with each syndrome will also be provided for searching in the
     directory.
    </p>
    <input type='hidden' name='syn-max' value='%d' />
    <table border='0' cellpadding='2' cellspacing='0' id='syndromes'>
""" % (gp.providesServices == True and " checked='checked'" or "",
       gp.providesServices == False and " checked='checked'" or "",
       gp.acceptsCalls == True and " checked='checked'" or "",
       gp.acceptsCalls == False and " checked='checked'" or "",
       gp.limitations and " checked='checked'" or "",
       gp.limitations and cgi.escape(gp.limitations) or "",
       not gp.limitations and " checked='checked'" or "",
       len(gp.lookupValues.Syndromes)))
    syndromes = gp.lookupValues.Syndromes
    numCols = 2
    numRows = len(syndromes) / numCols
    if len(syndromes) % numCols:
        numRows += 1
    for i in range(numRows):
        form.append(u"""\
     <tr>
""")
        for j in range(numCols):
            idx = numRows * j + i
            if idx < len(syndromes):
                syndrome = syndromes[idx]
                if syndrome in gp.syndromes:
                    checked = " checked='checked'"
                else:
                    checked = ""
                form.append(u"""\
      <td>
       <input type='checkbox' %s name='syn-%d' value='%s' />
       %s
      </td>
""" % (checked, idx + 1, clean(syndrome), cgi.escape(syndrome)))
        form.append(u"""\
     </tr>
""")
    form.append(u"""\
    </table>
    <br />

    <h1>9. Memberships</h1>
    <p class='instructions'>
     Please indicate your membership in any of the following national 
     societies or special interest groups.
    </p>
    <input type='hidden' name='memb-max' value='%d' />
    <br />
""" % len(gp.lookupValues.Societies))
    i = 1
    for society in gp.lookupValues.Societies:
        form.append(u"""\
    <input type='checkbox' class='indentedcb' value='%s'
           name='memb-%d' id='memb-%d'%s>%s<br />
""" % (clean(society), i, i,
       society in gp.societies and " checked='checked'" or "",
       cgi.escape(society)))
        i += 1

    form.append(u"""\
    <br />

    <h1>10. Completion</h1>
    <p class='instructions'>
     When you have reviewed the information above and made any
     necessary changes, please select the appropriate button to
     submit your reply.
    </p>
    <br />
    <input class='button' type='submit' name='Changes' value='Changes'/>
    &nbsp; Please update my profile with the changes I have made.<br /><br />
    <input class='button' type='submit' name='Unchanged' value='Unchanged'/>
    &nbsp; No changes are required.<br />&nbsp;
   </form>
""")
    sendPage(u"".join(form))

def saveChanges(gp):
    serialization = etree.tostring(gp.toElement())
    conn = util.getConnection('emailers')
    cursor = conn.cursor()
    cursor.execute("""\
        UPDATE gp_emailer
           SET xml = %s,
               completed = NOW()
         WHERE id = %s""", (serialization, gp.trackerId))
    conn.commit()

def markCompletion(gp):
    conn = util.getConnection('emailers')
    cursor = conn.cursor()
    cursor.execute("UPDATE gp_emailer SET completed = NOW() WHERE id = %s",
                   gp.trackerId)
    conn.commit()
    
def sayThankYou():
    sendPage(u"""\
   <p id='payload'>Thanks!</p>
""")

def bail(why):
    sendPage(u"""\
   <p id='payload' class='error'>Error: %s</p>
""" % cgi.escape(why))

def sendPage(payload):
    page = [u"""\
Content-type: text/html; charset=utf-8

<html>
 <head>
  <meta http-equiv='Content-type' content='text/html; charset=utf-8'>
  <title>NCI Cancer Genetics Services Directory</title>
  <style type='text/css'>
   * { font-family: Arial, sans-serif; font-size: 10pt; }
   body { text-align: center; margin: 0; padding: 0; }
   form, #payload { padding-left: 17px; }
   #payload { padding-top: 20px; padding-bottom: 20px; }

   h1 { color: #8f8c81; font-size: 12pt; margin-top: 30px; clear: left; }
   h2 { font-weight: normal; margin-left: 232px; text-decoration: underline }
   a { color: #333; text-decoration: none; }
   a:hover { color: #a80101; }
   img { border: none; margin: 0; padding: 0 }
   textarea { height: 70px; }

   /* Set the top background colors across entire page width. */
   #red-stripe, #grey-stripe {
       position: absolute; z-index: -1; left: 0px; width: 100%%;
       font-size: 1px;
   }
   #red-stripe  { background: #a80101; top:  0px; height: 79px; }
   #grey-stripe { background: #696657; top: 79px; height:  3px; }

   /* All the real content is centered on the page in a fixed-width block */
   #wrapper { margin-left: auto; margin-right: auto;
              width: 640px; text-align: left; }
   #limits { width: 600px; }
   #footer { text-align: center; padding-right: 30px; }
   .name { font-style: italic }
   .field, .cb { width: 300px; }
   .indentedcb { margin-left: 100px; }
   .label { float: left; width: 225px; margin-right: 5px;
            text-align: right; font-weight: bold; clear: left; }
   .button { margin-left: 50px; color: white; background: #a80101; 
             font-weight: bold; width: 8em; }
   .year   { border: none; }
   .error { color: red; font-weight: bold; }
   #syndromes td { padding-left: 50px; }
  </style>
 </head>
 <body>
  <div id='red-stripe'>&nbsp;</div>
  <div id='grey-stripe'>&nbsp;</div>
  <div id='wrapper'>
   <img src='@@IMAGES@@/nci-cgsd-banner.jpg' />
"""]
    page.append(payload)
    page.append(u"""\
   <div id='footer'>
    <a href='http://www.cancer.gov/'><img
       src='http://pdqupdate.cancer.gov/PDQUpdate/ctsimages/footer_nci.gif'
       width='63' height='31'
       alt='National Cancer Institute' border='0'></a>
    <a href='http://www.dhhs.gov/'><img
       src='http://pdqupdate.cancer.gov/PDQUpdate/ctsimages/footer_hhs.gif' 
       width='39' height='31'
       alt='Department of Health and Human Services' border='0'></a>
    <a href='http://www.nih.gov/'><img
       src='http://pdqupdate.cancer.gov/PDQUpdate/ctsimages/footer_nih.gif'
       width='46' height='31'
       alt='National Institutes of Health' border='0'></a>
    <a href='http://www.usa.gov/'><img
       src='http://pdqupdate.cancer.gov/PDQUpdate/ctsimages/footer_usagov.gif' 
       width='91' height='31'
       alt='USA.gov' border='0'></a>
    <br />&nbsp;
   </div>
  </div>
 </body>
</html>""")
    print util.fillPlaceholders(u"".join(page)).encode('utf-8')

def saving(fields):
    return fields.getvalue('Changes') or fields.getvalue('Unchanged')

def save(fields):
    gp = GP(fields=fields)
    if fields.getvalue('Changes'):
        saveChanges(gp)
        message = u"""\
GP mailer %d (Person CDR%d) was reviewed and submitted with changes
which can be reviewed at:

http://%s%s/ShowGPChanges.py?id=%d
""" % (gp.trackerId, gp.personId, util.WEB_HOST, util.CGI_BASE, gp.trackerId)
    else:
        markCompletion(gp)
        message = ("GP mailer %d was reviewed and submitted with no changes" %
                   gp.trackerId)
    recips = ('NCIGENETICSDIRECTORY@ICFI.COM', '***REMOVED***')
    subject = "GP mailer %d" % gp.trackerId
    util.sendMail(util.SENDER, recips, subject, message)
    sayThankYou()

def main():
    fields = cgi.FieldStorage()
    if saving(fields):
        save(fields)
    else:
        showForm(fields)

if __name__ == '__main__':
    try:
        main()
    except Exception, e:
        bail("%s" % e)
