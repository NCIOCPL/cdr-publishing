#!/usr/bin/python
#----------------------------------------------------------------------
#
# $Id$
#
# Sanity check for CDR configuration files for a given CBIIT tier.
#
#----------------------------------------------------------------------
import cdrutil
import socket

TIER = cdrutil.getTier()
HOSTING = cdrutil.getEnvironment()
APPHOST = cdrutil.AppHost(HOSTING, TIER)
ROLES = {
    #"APP": 22,
    "APPC": 443,
    "APPWEB": 443,
    "DBNIX": 3600,
    "EMAILERS": 22,
    "EMAILERSC": 443,
    "EMAILERSWEB": 443,
    "EMAILERSDB": 3600
}

DATABASES = {
    "dropbox": ("dropbox",),
    "emailers": ("emailers",),
}
def db_account_ok(db, account):
    try:
        conn = cdrutil.getConnection(db)
        #conn.close()
        return True
    except:
        #raise
        return False

class Host:
    def __init__(self, role):
        self.aname = self.ip = self.dns = self.error = None
        self.info = APPHOST.host.get(role)
        if not self.info:
            self.error = "MISSING"
        else:
            self.dns = ("%s.%s" % self.info).rstrip(".")
            try:
                self.ip = socket.gethostbyname(self.dns)
                try:
                    port = ROLES.get(role)
                    if port:
                        conn = socket.create_connection((self.dns, port))
                        conn.close()
                except:
                    self.error = "CONNECTION REFUSED"
            except:
                self.error = "NOT FOUND"

roles = []
databases = []
for role in sorted(ROLES):
    try:
        host = Host(role)
        roles.append((role, host.dns or "", host.ip or "", host.error))
    except Exception, e:
        roles.append((role, "", "", str(e)))
for db in sorted(DATABASES):
    for account in DATABASES[db]:
        databases.append((db, account, db_account_ok(db, account)))
print """\
Content-type: text/plain

%s""" % repr((roles, databases))
