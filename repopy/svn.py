import pysvn

from getpass import getpass

import repopy.config as config

class ClientError(pysvn.ClientError):
    pass

class Client(object):
    """Dispatcher class for the Subversion Client"""

    __client = None

    class LoginPrompt(object):
        """
        Callback object for the svn client.

        Saves the login information in memory until the Shell exits.
        """
        def __init__(self):
            self.username = None
            self.password = None

        def __call__(self, realm, username, maysave):
            if not self.username and not self.password:
                self.username = raw_input('>>> Subversion username for %s > ' % realm)
                self.password = getpass('>>> Subversion password for %s > ' % realm)

            return (True, self.username, self.password, False)


    class AcceptCertPrompt(object):
        """
        Callback object for the svn client.

        Saves whether or not the user accepted the svn server ssl cert
        in memory until the Shell exits.
        """
        # (
        #       Accept the cert?,
        #       Which failures to accept(noone knows what this means),
        #       Save the certificate if accepted? (We don't)
        # )
        ACCEPT = (True, 0, False)
        DENY = (False, 0, False)

        def __init__(self):
            self.save_accept = False

        def __call__(self, trust_dict):
            if self.save_accept:
                return self.ACCEPT

            print 'Trust SSL Certificate:?'
            print 'Hostname: %s' % trust_dict['hostname']
            print 'Realm: %s' % trust_dict['realm']
            print 'Valid from: %s' % trust_dict['valid_from']
            print 'Valid until: %s' % trust_dict['valid_until']

            accept_prompt = '>>> Accept this certificate? y/n '
            accept = raw_input(accept_prompt).lower().strip()

            while accept not in ('y', 'yes', 'n', 'no'):
                accept = raw_input(accept_prompt).lower().strip()

            if accept in ('n', 'no'):
                return self.DENY

            return self.ACCEPT


    def __init__(self):
        #Setup the subversion client with our prompt messages
        if self.__client is None:
            self.__client = pysvn.Client()
            self.__client.callback_get_login = Client.LoginPrompt()
            self.__client.callback_ssl_server_trust_prompt = Client.AcceptCertPrompt()


    def add(self, path):
        if config.MOCK_SVN_COMMANDS:
            print 'SVNCient.add()'
            print '\tpath: %s' % path
        else:
            return self.__client.add(path)

    def checkin(self, paths, message):
        if config.MOCK_SVN_COMMANDS:
            print 'SVNCient.checkin()'
            print '\tpaths: %s' % ', '.join(paths)
            print '\tmessage: %s' % message
        else:
            return self.__client.checkin(paths, message)

    def remove(self, path):
        if config.MOCK_SVN_COMMANDS:
            print 'SVNCient.remove()'
            print '\tpath: %s' % path
        else:
            return self.__client.remove(path)
