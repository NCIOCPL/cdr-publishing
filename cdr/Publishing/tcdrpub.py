import cdr, cdrpub
try:
    subsetName = 'PDQ Editorial Board Members Mailing'
    session = cdr.login('rmk', '***REDACTED***')
except Exception, eInfo:
    print "Ouch!  %s" % str(eInfo)
if 1:
    docIds = ((190793,1),
              (190794,1),
              (190832,1),
              (190899,1),
              (190912,1),
              (190929,3))
    parms = (('Board', 'Breast Cancer Editorial Board'),)
    email = '***REMOVED***'
    res = cdrpub.initNewJob(266328, subsetName, session, docIds, parms,
                            email)
    if type(res) == type(""):
        print "Bad news... %s" % res
    elif type(res) == type(u''):
        print u"Bad News... %s" % res
    else:
        (id, dir) = res
        print "id=%d dir=%s" % (id, dir)
