"""
Configuration for repopy modules.
"""

import commands
import os

APACHE_USER = 'apache'
APACHE_GROUP = 'users'
APACHE_CONF_ROOT = '/etc/httpd/conf/repos.d'

SVN_SERVER = 'svn.example.com'
URL_PREFIX = 'https://'
SVN_PREFIX = 'svn'

REPO_ROOT = '/repos'
YAML_ROOT = os.path.join(REPO_ROOT, 'yaml')
SVNADMIN = commands.getoutput("which svnadmin")
VERBOSE = 1
NON_LDAP_USERS = ['test1']
TEMPLATE_DIR = 'templates'

MOCK_SVN_COMMANDS = True

FISHEYE_ADMIN_URL = 'https://example.com/fisheye/admin'
FISHEYE_ADMIN_PW = 'XXXXXXXX'

SMTP_HOST = 'localhost'
EMAIL_DOMAIN = 'example.com'
EMAIL_FROM = 'svn.admins@example.com'