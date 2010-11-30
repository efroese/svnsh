import sys
import optparse
import new
import exceptions
import logging
import os
import shutil
import tarfile
import operator

import yaml

from getpass import getpass
from optparse import OptionParser, make_option

import config

from repository import Repository, Auth, Group
from templates import apache_conf
from utils import addauth_email
from svn import Client
from fisheye import FisheyeAdmin
from errors import CommandError, CommandArgumentError, CommandOptionError

class CommandOptionParser(OptionParser):
    """OptionParser subclass for use in Commands."""
    def error(self, msg):
        self.print_usage(sys.stderr)
        raise CommandOptionError("Invalid command syntax.")


class ArgumentCount(object):
    """The number of arguments required by a Command."""

    def __init__(self, value, cmp=operator.eq):
        """
        Create an argument count constraint.

        value is the number of arguments required. cmp is the function
        used to compare value to the actual number of arguments. The
        default comparison is operator.eq (==).
        """
        self.value = value
        self.cmp = cmp

    def validate(self, args):
        return self.cmp(len(args), self.value)

###############################################################################
# Functions that write out configuration files or descriptors

def __check_path_dir(repo):
    """
    Make sure all of the directories we need to write out the repository
    and YAML files exist.
    """
    yaml_dir = os.path.dirname(repo.yaml_path)
    repo_dir = os.path.dirname(repo.path_to_repo)

    if not os.path.exists(yaml_dir):
        try:
            os.makedirs(yaml_dir)
        except Exception, e:
            raise CommandError('Error creating directory at %s: %s' % (yaml_dir, str(e)))
        svn_client.add(yaml_dir)

    if not os.path.exists(repo_dir):
        try:
            os.makedirs(repo_dir)
        except Exception, e:
            raise CommandError('Error creating directory at %s: %s' % (repo_dir, str(e)))

    svn_client.checkin([yaml_dir], 'Add directory %s for %s yaml files.' % (yaml_dir, repo.prefix) )

def __write_repository_yaml(repo):
    try:
        f = file(repo.yaml_path, 'w')
        yaml.dump(repo, f)
        f.close()
        print 'Wrote yaml descriptor for %s.' % repo.name
    except Exception, e:
        raise CommandError('Unable to dump %s to yaml: %s.'  % (repo.name, e))

def __write_repository_fisheyeauth(repo):
    """
    Write out a simple file describing which users should be allowed
    to view a fisheye site. Anyone with read access to / will be allowed.

    Raises a CommandError exception if an error occurs.
    """
    if not repo.fisheye:
        return

    users = []
    for auth in repo.authorizations:
        if auth.path == '/':
            #expand if the user is a group: auth.user == '@xxx'
            if auth.user[0] == '@':
                for group in repo.groups:
                    if group.name == auth.user[1:]:#find the right group
                        for user in group.members:
                            users.append(user)
                        break
            else:
                users.append(auth.user)

    try:
        f = file(repo.fisheye_auth_path, 'w')
        f.write('\n'.join(users) + '\n')
        f.close()
        print 'Wrote fisheye auth file for %s.' % repo.name
    except Exception, e:
        raise CommandError('Unable to save fisheye auth: %s.'  % (e))

def __write_authz(repo):
    """
    Convenience method to call to write out the apache authz and throw a
    CommandError if it fails.
    """
    try:
        repo.write_authz()
    except Error, e:
        raise CommandError( "Error writing the authz file: %s." % e)


###############################################################################
# SVN YAML functions.
svn_client = Client()

def __add_yaml(repo):
    """Add a YAML file to the SVN repository that logs our transactions."""
    try:
        svn_client.add(repo.yaml_path)
    except Exception, e:
        raise CommandError( "Error adding the yaml descriptor: %s." % e)


def __checkin_yaml(repo, message):
    """Commit the YAML to the SVN repository that logs our transactions."""
    try:
        rev = svn_client.checkin([repo.yaml_path], message)
        if not rev:
            print 'Nothing to commit for %s.' % repo.yaml_path
        else:
            print 'Descriptor for %s commited. Repository at revision %d.' % \
                                                    (repo.path, rev.number)
    except Exception, e:
        raise CommandError('Error committing the yaml descriptor: %s.' % e)

###############################################################################
# Functions that deal with reading in YAML and parsing args.
def __parse_prefix_name(path):
    """
    Given a symbolic path to a repository return the prefix and name

    >>> __parse_prefix_name('/sakai')
    ('', 'sakai')
    >>> __parse_prefix_name('sakai')
    ('', 'sakai')
    >>> __parse_prefix_name('/its/sakai')
    ('its', 'sakai')
    >>> __parse_prefix_name('/its/some/sakai')
    ('its/some', 'sakai')
    """
    splits = path.split('/')
    if len(splits) == 1:
        return ('', splits[0])
    else:
        # Filters out empty entries
        splits = [x for x in splits if x]
        prefix = '/'.join(splits[:-1])
        name = splits[-1]
        return (prefix, name)

def __load_repository_from_yaml(prefix, name):
    """
    Load a repository given the name and prefix.
    Raises a CommandError exception if an error occurs.
    """
    try:
        repo = yaml.load( open(os.path.join(config.YAML_ROOT,
                                      prefix,
                                      name + '.yaml'), 'r').read() )
    except Exception, e:
        raise CommandError('There was an error loading the repository description.',
                           'The original error was: %s' % e)
    return repo

###############################################################################
def __get_description():
    description = ""
    while description == "":
        description = raw_input(">>> Please enter a short description for the repo.\n")
        description = description.strip()

    return description

# Shell reads this to determine the list of commands available
__all__ = []

class Command (object):
    """Base class for shell commands."""

    def __init__(self, name, usage, description, options, run, arg_count=None):
        """
        Initialize the Command.

        Create a CommandOptionParser as well as registering the
        command with the __all__ variable.
        """

        self.name = name
        self.usage = usage
        self.description = description
        self.options = options

        self._run = new.instancemethod(run, self, self.__class__)
        self.parser = CommandOptionParser(usage=self.usage,
                                          description=self.description,
                                          option_list=self.options)
        self.arg_count = arg_count

        self._register()


    def __call__(self, argv):
        self.run(argv)


    def _register(self):
        if self.name in __all__:
            return
        __all__.append(self.name)


    def help(self):
        self.parser.print_help()


    def run(self, argv):
        (options, args) = self.parser.parse_args(args=argv)
        if self.arg_count and not self.arg_count.validate(args):
            raise CommandArgumentError('Incorrect number of arguments.\n')
        self._run(options, args)

###############################################################################
def _run_create(self, options, args):
    """
    Create the repository.
    Save the yaml descriptor.
    """

    prefix, name = __parse_prefix_name(args[0])
    print "Name = %s" % name
    if prefix:
        print "Prefix = %s" % prefix
    print "Fisheye = %s" % options.fisheye

    repo = Repository(prefix, name, options.fisheye)
    if Repository.exists(repo.path_to_repo):
        raise CommandError('A repository named "%s" already exists.' % repo.path)
    try:
        __check_path_dir(repo)
        print 'Creating the repository ...'
        repo.create()
        print 'Created the repository'
        print repo.apache_conf
        apache_conf.process_to_file(repo.apache_conf,
                                    {'repopath' : repo.path,
                                     'users' : ', '.join(repo.users()),
                                     'apache_authz_path' : repo.apache_authz})
        print "Created apache conf"
        __write_repository_yaml(repo)
        print "CREATED repository at %s." % repo.path

        if options.fisheye:
            __write_repository_fisheyeauth(repo)
            fisheye_admin = FisheyeAdmin(password=config.FISHEYE_ADMIN_PW)
            if fisheye_admin.create_repository(repo, __get_description()):
                print "Successfully created a fisheye instance for %s" % repo.name

    except Exception, e:
        raise CommandError("Failed to create the repository at %s\n" % repo.path_to_repo,
                           "The original error was: %s: %s" % (type(e), e))

    __add_yaml(repo)
    __checkin_yaml(repo, ('Create repository: %s.' % (repo.path_to_repo)))


create = Command(name='create',
                 usage='create path/name',
                 description='create: Create a new Subversion repository.',
                 options = [ make_option('-f', '--fisheye',
                               action='store_true',
                               dest='fisheye',
                               default=False,
                               help='Enable fisheye access to the new repository.') ],
                 run=_run_create,
                 arg_count=ArgumentCount(1)
                 )
###############################################################################

def _run_delete(self, options, args):
    """ Backup and delete the repository"""

    prefix, name = __parse_prefix_name(args[0])
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print ''

    repo = __load_repository_from_yaml(prefix,name)

    print 'We do this by hand.'
    print 'Delete the apache files:'
    print repo.apache_authz
    print repo.apache_conf
    print ''

    print 'Delete the yaml descriptor:'
    print repo.yaml_path
    print ''

    if repo.fisheye:
        print 'Delete the fisheye auth file.'
        print repo.fisheye_auth_path

    print 'Tar up the repository:'
    print 'tar czvf %s.tgz %s' % (repo.name, repo.path_to_repo)
    print ''

    print 'Restart apache.'


delete = Command(name='delete',
                 usage='delete path/name',
                 description='delete: Backup and remove Subversion repository.',
                 options = [ ],
                 run=_run_delete,
                 arg_count=ArgumentCount(1)
                 )
###############################################################################

def _run_add_auth(self, options, args):
    """Add an authorization to the repository"""

    name, path, user, mode = args

    if not mode in Auth.MODES:
        raise CommandError('Invalid authorization type. Please enter one fo the following: %s.'
                                                                        % ', '.join(Auth.MODES))
    prefix, name = __parse_prefix_name(name)
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print "Path = %s" % path
    print "User = %s" % user
    print "Mode = %s" % mode

    repo = __load_repository_from_yaml(prefix, name)
    try:
        repo.add_auth(path, user, mode)
    except ValueError, e:
        raise CommandError('Cannot add auth: %s.' % e )

    print 'Add Auth (%s, %s, %s)' % (path, user, mode)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    __checkin_yaml(repo, 'Add Auth (%s, %s, %s) to repository: %s.' %
                            (path, user, mode, repo.path))
    addauth_email(user, repo, path, mode)


addauth = Command(name='addauth',
                  usage='addauth path/name PATH USER MODE',
                  description='addauth: Authorize USER for MODE permission on REPO',
                  options=[],
                  run=_run_add_auth,
                  arg_count=ArgumentCount(4)
                  )
###############################################################################

def _run_del_auth(self, options, args):
    """
    Remove an authorization from the repository.
    Save the yaml descriptor file
    """

    name, path, user = args
    prefix, name = __parse_prefix_name(name)
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print "Path = %s" % path
    print "User = %s" % user

    repo = __load_repository_from_yaml(prefix, name)

    found = False
    for auth_mode in Auth.MODES:
        if repo.has_auth(path, user, auth_mode):
            found = True
            break

    if not found:
        raise CommandError('No Authorizations found for %s on %s in %s.' % (user, path, name))

    num_auths = len(repo.authorizations)
    repo.remove_auth(path, user)
    num_removed = num_auths - len(repo.authorizations)

    print "Removed %d permission%s for %s from %s." % (num_removed, (num_removed > 1) and 's' or '', user, name)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    __checkin_yaml(repo,'Delete Auth (%s, %s) from repository: %s.' %
                            (path, user, repo.path))


delauth = Command(name='delauth',
                  usage='delauth [-d DEPT] REPO PATH USER',
                  description='delauth: Remove a users permission for a path',
                  options=[],
                  run = _run_del_auth,
                  arg_count = ArgumentCount(3)
                  )
###############################################################################

def _run_del_user(self, options, args):
    """
    Delete all of a user's permissions from the repository
    Save the yaml descriptor file.
    """

    name, user = args
    prefix, name = __parse_prefix_name(name)
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print "User = %s" % user

    repo = __load_repository_from_yaml(prefix, name)
    num_auths_orig = len(repo.authorizations)
    repo.remove_user(user)
    num_removed = num_auths_orig - len(repo.authorizations)

    if num_removed == 0:
        raise CommandError('%s has no permissions for the repository %s' % (user, name))

    print "Removed %d permission%s for %s from %s" % (num_removed, (num_removed > 1) and 's' or '', user, name)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    __checkin_yaml(repo, 'Del User %s from repository: %s.' % (user, repo.path))


deluser = Command(name='deluser',
                  usage='deluser [-d DEPT] REPO USER',
                  description='deluser: Remove all permissions for a user on the repository.',
                  options=[],
                  run=_run_del_user,
                  arg_count=ArgumentCount(2)
                  )
###############################################################################

def _run_ls_auth(self, options, args):
    """Print all authorizations for a repository."""

    prefix, name = __parse_prefix_name(args[0])
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix

    repo = __load_repository_from_yaml(prefix, name)

    if len(repo.groups) > 0:
        print 'Groups:'
        for group in repo.groups:
            print '%s: %s' % (group.name, ', '.join(group.members))

    repo.authorizations.sort()
    if len(repo.authorizations) == 0:
        print "No authorizations!"
    for auth in repo.authorizations:
        print 'path: %s\tuser: %s\tpermission: %s.' % (auth.path, auth.user, auth.mode)

lsauth = Command(name='lsauth',
                 usage='lsauth [prefix/]name',
                 description='lsauth: List all permissions granted in a repository.',
                 options=[],
                 run=_run_ls_auth,
                 arg_count=ArgumentCount(1)
                 )
###############################################################################

def _run_add_group(self, options, args):
    """Add a group to the repository."""

    name, groupname = args[0:2]
    users = args[2:]

    tmpusers = []
    for user in users:
        tmpusers.append(user.strip(' ,:\t\n'))
    users = tmpusers

    prefix, name = __parse_prefix_name(name)
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print "Group = %s" % groupname
    print "Users = %s" % ', '.join(users)

    repo = __load_repository_from_yaml(prefix, name)

    repo.groups.append(Group(groupname, users))
    print "Added group %s to %s with members:" % (name, groupname)
    print '\n'.join(users)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    __checkin_yaml(repo,'Add group (name:%s, users:%s) to repository: %s.' %
                                (groupname, ', '.join(users), repo.path))

addgroup = Command(name='addgroup',
                   usage='addgroup [prefix/]name GROUPNAME USER1[ USER2 ...]',
                   description='addgroup: Add a group with users.',
                   options=[ ],
                   run=_run_add_group,
                   arg_count=ArgumentCount(3, operator.ge)
                   )
###############################################################################

def _run_del_group(self, options, args):
    """Delete a group from the repository."""

    name, groupname = args[0:2]
    users = None
    if len(args) > 2:
        users = args[2:]

    prefix, name = __parse_prefix_name(name)
    print "Name = %s" % name
    if prefix: print "Prefix = %s" % prefix
    print "Group = %s" % groupname
    if users: print "Users = %s" % ', '.join(users)

    repo = __load_repository_from_yaml(prefix, name)

    if not users:
        if raw_input('Do you want to remove this group and all its privileges? y/N ').lower() in ('y', 'yes'):
            repo.remove_group(groupname)
            print "Removed the group %s" % groupname
    else:
        for g in repos.groups:
            if g.name == groupname:
                for u in users: g.remove(u)
                break
        print "Removed users %s from group %s." % (' ,'.join(users), groupname)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    __checkin_yaml(repo, 'Delete Group:%s from repository: %s.' %
                                (groupname, repo.path))

delgroup = Command(name='delgroup',
                   usage='delgroup [prefix/]name REPO GROUPNAME [USER1[,USER2,...]]',
                   description='delgroup: Delete users from a group or the whole group and its permissions.',
                   options=[],
                   run = _run_del_group,
                   arg_count=ArgumentCount(2, operator.ge)
                   )
###############################################################################

def _run_commit(self, options, args):
    """Commit the repository yaml descriptor file."""
    prefix, name = __parse_prefix_name(args[0])
    try:
        repo = __load_repository_from_yaml(prefix, name)
    except CommandError:
        repo = Repository(prefix, name)

    if not Repository.exists(repo.path_to_repo):
        raise CommandError('Cannot commit a descriptor for a repo that doesn\'t exist.')

    if(options.add):
        __add_yaml(repo)
    __checkin_yaml(repo, "Committing yaml descriptor for %s." % repo.path)

commit = Command(name='commit',
                   usage='commit [-a] [prefix/]name',
                   description='commit: Commit the yaml descriptor for the repository.',
                   options=[ make_option('-a', '--add',
            					dest='add',
            					action='store_true',
            					default=False,
            					help='Add the yaml descriptor to the config repository.'),
                             ],
                   run = _run_commit,
                   arg_count=ArgumentCount(1)
                   )
###############################################################################

def _run_ls(self, options, args):
    def print_repos(prefix):
        paths = os.listdir(os.path.join(config.REPO_ROOT, prefix))
        print "\n[ Repositories in %s ]" % os.path.join(config.REPO_ROOT, prefix)
        paths.sort()
        for path in paths:
            if Repository.exists(os.path.join(config.REPO_ROOT, prefix, path)):
                print path

    if len(args) == 1:
        print_repos(args[0])

    else:
        prefixes = os.listdir(config.REPO_ROOT)
        for folder in ('bin', 'yaml', '.svn'):
            try:
                prefixes.remove(folder)
            except ValueError, e:
                pass

        prefixes.sort()
        for prefix in prefixes:
            print_repos(prefix)


ls = Command(name='ls',
               usage='ls [prefix/]',
               description='ls: List all repsositories with a certain prefix or them all of no prefix',
               options=[],
               run = _run_ls,
               arg_count=ArgumentCount(0, operator.ge)
               )
###############################################################################

def _run_flush(self, options, args):

    prefix, name = __parse_prefix_name(args[0])
    repo = __load_repository_from_yaml(prefix, name)

    __write_repository_yaml(repo)
    __write_repository_fisheyeauth(repo)
    __write_authz(repo)
    print 'Wrote apache authz.'
    apache_conf.process_to_file(repo.apache_conf,
                                    {'repopath' : repo.path,
                                     'users' : ', '.join(repo.users()),
                                     'apache_authz_path' : repo.apache_authz})
    print 'Wrote apache conf.'


flush = Command(name='flush',
                   usage='flush [prefix/]name',
                   description='flush: write out yaml, fisheyeauth, apache conf, and apache authz.',
                   options=[],
                   run = _run_flush,
                   arg_count=ArgumentCount(1)
                   )
###############################################################################

def _run_fisheye(self, options, args):
    mode = 'check'
    prefix, name = __parse_prefix_name(args[0])

    if len(args) > 1:
        mode = args[1].lower()

    if not mode in ('on', 'off', 'check'):
        raise CommandArgumentError('fisheye: Enter either on or off.')

    repo = __load_repository_from_yaml(prefix, name)
    fisheye_admin = FisheyeAdmin(config.FISHEYE_ADMIN_PW)

    if mode == 'on':
        if repo.fisheye == True:
            print 'Fisheye is already turned on for %s.' % repo.name
            return
        else:
            repo.fisheye = True
            repo.set_fisheye_auth_path()
            if fisheye_admin.create_repository(repo, __get_description()):
                print "Successfully create a fisheye instance for %s" % repo.name
            else:
                print "Failed to create a fisheye instance for %s. Please do it by hand." % repo.name
            commit_message = 'Turned fisheye ON for %s.' % name

    elif mode == "off":
        if repo.fisheye == False:
            print 'Fisheye is already turned off for %s.' % repo.name
            return
        else:
            repo.fisheye = False
            if fisheye_admin.delete_repository(repo):
                print "Successfully deleted the fisheye instance for %s" % repo.name
            else:
                print "Failed to delete the fisheye instance for %s. Please do it by hand." % repo.name
            commit_message = 'Turned fisheye OFF for %s.' % name
    else:
        print 'Fisheye is %s for %s' % (repo.fisheye and 'ON' or 'OFF', repo.name)
        return

    __write_repository_yaml(repo)
    __checkin_yaml(repo, commit_message)

    if repo.fisheye:
        __write_repository_fisheyeauth(repo)
    else:
        try:
            os.remove(repo.fisheye_auth_path)
        except Exception, e:
            raise CommandError('Error removing fisheye auth file at: %s \n%s' % (repo.fisheye_auth_path, e) )

fisheye = Command(name='fisheye',
                   usage='fisheye [prefix/name] on|off|check',
                   description='fisheye: Enable or disable fisheye authorization file.',
                   options=[ ],
                   run = _run_fisheye,
                   arg_count=ArgumentCount(1, operator.ge)
                   )
###############################################################################

def _run_info(self, options, args):
    prefix, name = __parse_prefix_name(args[0])
    repo = __load_repository_from_yaml(prefix, name)

    print 'Repository summary:'
    print ''
    print 'Name: %s' % name
    if prefix: print "Prefix = %s" % prefix
    print 'URL: %s%s/%s/%s' % (config.URL_PREFIX, config.SVN_SERVER,
                                config.SVN_PREFIX, repo.path)

    print 'Fisheye status: %s' % (repo.fisheye and 'on' or 'off')
    if options.verbose:
        print ''
        print 'Path: %s' % repo.path
        print 'Yaml file: %s' % repo.yaml_path
        print 'Apache Config: %s' % repo.apache_conf
        print 'Apache Authz: %s' % repo.apache_authz
        print ''

        if repo.fisheye:
            print 'Fisheye auth file: %s' % repo.fisheye_auth_path
        print ''

    if len(repo.groups) > 0:
        print 'Groups:'
        for group in repo.groups:
            print '%s = %s' % (group.name, ', '.join(group.members))
        print ''

    repo.authorizations.sort()
    if len(repo.authorizations) == 0:
        print "No authorizations!"
    else:
        print 'Authorizations:'
    for auth in repo.authorizations:
        print 'path: %s\tuser: %s\tpermission: %s' % (auth.path, auth.user, auth.mode)

info = Command(name='info',
                   usage='info [prefix/]name',
                   description='info: Print info about a repository.',
                   options=[ make_option('-v', action="store_true", dest='verbose',
                                          help='Print verbose info about a repository.'),
                             ],
                   run = _run_info,
                   arg_count=ArgumentCount(1)
                   )
###############################################################################

def _test():
   import doctest
   doctest.testmod()

if __name__ == '__main__':
   _test()
