#!/usr/bin/env python
# encoding: utf-8
"""
import.py

Created by Erik Froese on 2006-09-25.
"""

import sys
import os
import yaml

from optparse import OptionParser, make_option

from repopy.repository import Repository, Auth, Group
from repopy.svn import Client

help_message = '''
importrepo.py
Import an existing authz file into our yaml representation.
usage: import.py -d department repository
'''



class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def get_params(argv=None):

    options = [ make_option('-d', '--department',
                            type='string',
                            dest='department',
                            default='its',
                            help='Department the repo belings to.'),
                            ]

    parser = OptionParser(usage=help_message,
                        description='Import existing repos.',
                        option_list=options)

    (options, args) = parser.parse_args(args=argv[1:])
    if not len(args) == 1:
        raise Usage('Incorrect number of arguments.')

    return(args[0], options.department)


def _get_chunks(lines):
    chunk_indexes = []

    i = 0
    while i < len(lines):
        if lines[i].startswith("["):
            chunk_indexes.append(i)
        i += 1

    chunks = []
    for i in range(len(chunk_indexes)):
        if i == len(chunk_indexes) - 1:
            chunks.append(lines[chunk_indexes[i]:])
        else:
            chunks.append(lines[chunk_indexes[i]:chunk_indexes[i+1]])

    return chunks


def _read_authorizations(repo):
    if repo == None:
        raise exception('No repository.')

    try:
        lines = open( repo.apache_authz, 'r').readlines()
    except IOError:
        raise Exception('_read_authz(): No configuration file found at %s' % repo.apache_authz)

    lines = filter(lambda l: not l.strip() == '', lines)
    chunks = _get_chunks(lines)

    authorizations = []
    print 'Authorizations:'
    for chunk in chunks:
        if chunk[0] == '[groups]':
            continue

        path = chunk[0]
        path = path.replace('[','')
        path = path.replace(']','')
        path = path.strip()
        for line in chunk[1:]:
            try:
                user, mode = line.split('=')
                user = user.strip()
                mode = mode.strip()
            except ValueError:
                print 'Malformed permission at %s. %s' % (line, e)
                continue
            try:
                print 'Add Auth( %s, %s, %s )' % (path, user, mode)
                authorizations.append( Auth(path, user, mode) )
            except ValueError, e:
                print 'Malformed permission: %s. %s' % (line, e)

    print ''

    return authorizations


def _read_groups(repo):
    if repo == None:
        raise exception('No repository.')

    try:
        lines = open( repo.apache_authz, 'r').readlines()
    except IOError:
        raise Exception('_read_authz(): No configuration file found at %s' % repo.apache_authz )

    groups = []

    lines = filter(lambda l: not l.strip() == '', lines)
    chunks = _get_chunks(lines)

    for chunk in chunks:
        if chunk[0] == '[groups]':
            print 'Groups:'
            for line in chunk[1:]:
                try:
                    groupname, users = line.split("=")
                except ValueError:
                    continue
                groupname = groupname.strip()
                g_users = []
                for u in users.split(","):
                    u = u.strip()
                    if not u == '': g_users.append(u)

                print '%s: %s' % (groupname,  ', '.join(g_users))
                groups.append(Group(groupname, g_users))
            print ''

    return groups

if __name__ == "__main__":
    name = None
    department = None
    try:
        name, department = get_params(sys.argv)
    except Exception, e:
        print e
        print help_message
        sys.exit(1)

    repo = Repository(name, department)
    repo.groups = _read_groups(repo)
    repo.authorizations = _read_authorizations(repo)

    try:
        f = file(repo.yaml_path, 'w')
        yaml.dump(repo, f)
        f.close()
    except Exception, e:
        raise Exception('Unable to dump %s to yaml: %s'  % (repo.name, e))

    try:
        svn_client = Client()
        svn_client.add(repo.yaml_path)
        svn_client.checkin([repo.yaml_path], 'Add yaml descriptor after importing %s' % repo.name)
    except Exception, e:
        raise Exception('Unable to commit yaml descriptor to SVN: %s' % e)

    print 'Import complete.'
    print 'Name: %s ' % repo.name
    print 'Department: %s ' % repo.department
    print 'Authorizations imported: %d' % len(repo.authorizations)
    print 'Groups imported: %d' % len(repo.groups)

    sys.exit(0)
