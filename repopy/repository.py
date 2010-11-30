import os
import shutil
import commands
import tarfile
import sets
import itertools
import yaml

from pwd import getpwnam

import config

def _run_command(cmd):
    status, output = commands.getstatusoutput(cmd)
    if config.VERBOSE:
        print cmd
        print output

    if not status == 0:
        raise Exception, output
    return (status, output)

# The prefix could be None or a string of the form "some/path/to"
def _make_path(prefix, name, sep="/"):
    if not prefix:
        return name
    return "%s%s%s" % (prefix.strip('/'), sep, name)

class RepositoryException(Exception):
    pass

class SVNRepositoryException(RepositoryException):
    pass

class Repository (object):
    """A Subversion repository."""

    def __init__(self, prefix, name, fisheye=False):
        if not prefix:
            self.prefix = ''
        else:
            self.prefix = prefix
        self.name = name
        self.fisheye = fisheye
        self.authorizations = []
        self.groups = []
        self.yaml_path = os.path.join(config.YAML_ROOT,
                                        _make_path(prefix, name) + '.yaml')
        self.fisheye_auth_path = os.path.join(config.YAML_ROOT,
                                        _make_path(prefix, name) + '.fisheyeauth')
        self.fisheye_name = _make_path(prefix, name, sep="_")

        apache_base = os.path.join(config.APACHE_CONF_ROOT,
                                    _make_path(prefix, name, sep="_"))
        self.apache_authz = apache_base + ".authz"
        self.apache_conf = apache_base + ".conf"

    def _get_path(self):
        return _make_path(self.prefix, self.name)
    path = property(_get_path)

    def _path_to_repo(self):
        """Where is this Repository located on the filesystem?"""
        return os.path.join(config.REPO_ROOT, _make_path(self.prefix, self.name))
    path_to_repo = property(_path_to_repo)

    def dump(self, filename):
        cmd = "%s dump %s > %s" % (config.SVNADMIN, self.path_to_repo, filename)
        _run_command(cmd)

    def create(self):
        """Create the repository on the filesystem."""
        try:
            apache_uid, apache_gid = getpwnam(config.APACHE_USER)[2:4]
        except KeyError, e:
            raise SVNRepositoryException('No passwd entry for Apache user: %s' % config.APACHE_USER)

        os.makedirs(self.path_to_repo)
        print 'Create %s' % self.path_to_repo
        cmd = "%s --fs-type fsfs create %s" % (config.SVNADMIN, self.path_to_repo)
        status, output = _run_command(cmd)

        if not status == 0:
            raise SVNRepositoryException('Error creating repository with svnadmin: %s' % output)

        os.chown(self.path_to_repo, apache_uid, apache_gid)
        for root, dirs, files in os.walk(self.path_to_repo):
            for path in [ os.path.join(root, f) for f in dirs + files]:
                os.chown(path, apache_uid, apache_gid)
                print "ownership of '%s' set to '%s:%s'" % (self.path_to_repo,
                                                            config.APACHE_USER,
                                                            config.APACHE_GROUP)


    def exists(path):
        """Determine if the path given is already a repository."""
        if os.path.exists(path):
            try:
                files = os.listdir(path)
                if "conf" in files and "format" in files:
                    return True
            except OSError:
                return False

        return False

    exists = staticmethod(exists)

    def delete(self):
        """Delete a repository from the filesystem."""
        shutil.rmtree(self.path)
        os.remove(self.apache_authz)
        os.remove(self.apache_conf)

    def add_auth(self, path_in_repo, user, mode):
        """
        Add an authorization to the repository.

        >>> r = Repository('bar', 'foo', False)
        >>> r.add_auth('/one', 'arthur', Auth.READ_WRITE)
        >>> r.authorizations
        [Auth(/one, arthur, rw)]
        >>> r.groups.append(Group('tg1', ['foo', 'bar']))
        >>> r.add_auth('/one', '@tg1', Auth.READ_WRITE)
        >>> r.add_auth('/one', '@arthur', Auth.READ_WRITE)
        Traceback (most recent call last):
        ...
        ValueError: Group @arthur is not a valid group for this repository.
        """

        if user[0] == '@' and user[1:] not in [g.name for g in self.groups]:
            raise ValueError('Group %s is not a valid group for this repository.' % user)

        if self.has_auth(path_in_repo, user, mode ):
            raise ValueError('Auth( %s, %s, %s ) already exists.' % \
                                (path_in_repo, user, mode))

        self.authorizations.append(Auth(path_in_repo, user, mode))
        self.authorizations.sort()

    def authz(self):
        """ Make an string to write to an authz file."""
        l = []

        if len(self.groups) > 0:
            l.append('[groups]')
        for group in self.groups:
            if len(group.members) > 0 :
                l.append( "%s = %s" % (group.name, ", ".join(group.members)) )

        l.append('')
        paths = dict([ (a.path,1) for a in self.authorizations ]).keys()
        paths.sort()
        for path in paths:
            l.append('[%s]' % path)
            for auth in self.authorizations:
                if auth.path == path:
                    l.append('%s = %s' % (auth.user, auth.mode))
            l.append('')

        return '\n'.join(l) + "\n"


    def has_auth(self, path_in_repo, user, mode):
        """
        Check if an authorization exists
        >>> r = Repository("test_repo", "test_dept", False)
        >>> r.add_auth('/test1', 'test_user1', Auth.READ_WRITE)
        >>> r.has_auth('/test1', 'test_user1', Auth.READ_WRITE)
        True
        >>> r.has_auth('/test1', 'test_user', Auth.READ_WRITE)
        False
        """
        if user[0] == '@' and user[1:] not in [g.name for g in self.groups]:
            raise ValueError('Group %s is not a valid group for this repository.' % user)

        for auth in self.authorizations:
            if auth.path == path_in_repo and auth.user == user and auth.mode == mode:
                return True

        return False

    def remove_auth(self, path_in_repo, user):
        """
        Remove a specific authorization from the repository.

        >>> r = Repository("test_repo", "test_dept", False)
        >>> r.add_auth('/test1', 'test_user1', Auth.READ_WRITE)
        >>> r.add_auth('/test1', 'test_user2', Auth.READ_WRITE)
        >>> r.add_auth('/test2', 'test_user2', Auth.READ_WRITE)
        >>> r.remove_auth('/test1', 'test_user2')
        >>> r.authorizations
        [Auth(/test1, test_user1, rw), Auth(/test2, test_user2, rw)]

        """
        self.authorizations = [ a for a in self.authorizations if not (a.user == user and
                                                                    a.path == path_in_repo) ]

    def remove_group(self, group):
        """
        Remove a group and its permissions
        >>> r = Repository("test_repo", "test_dept", False)
        >>> r.groups.append(Group('tgroup1', ['tu1', 'tu2']))
        >>> r.groups.append(Group('tgroup2', ['tu3', 'tu1']))
        >>> r.add_auth('/test1', '@tgroup1', Auth.READ_WRITE)
        >>> r.add_auth('/test1', '@tgroup2', Auth.READ_WRITE)
        >>> r.add_auth('/test2', '@tgroup1', Auth.READ_WRITE)
        >>> r.remove_group('tgroup1')
        >>> r.groups
        [Group(tgroup2, ['tu3', 'tu1'])]
        >>> r.authorizations
        [Auth(/test1, @tgroup2, rw)]
        """

        self.groups = filter(lambda g: not g.name == group, self.groups)
        self.authorizations = filter(lambda a: a.user != ('@%s' % group), self.authorizations)


    def remove_user(self, user):
        """
        Remove all of a users permissions.

        >>> r = Repository('bar', 'foo', False)
        >>> r.add_auth('/one', 'arthur', Auth.READ_WRITE)
        >>> r.add_auth('/one', 'ford', Auth.READ_WRITE)
        >>> r.add_auth('/two', 'ford', Auth.READ_WRITE)
        >>> r.remove_user('ford')
        >>> r.authorizations
        [Auth(/one, arthur, rw)]
        >>> r.remove_user('arthur')
        >>> r.authorizations
        []

        """
        self.authorizations = filter(lambda a: a.user != user,
                                     self.authorizations)


    def users(self):
        """
        Get a list of all the users who can access a repository.
        Test Groups

        >>> r = Repository("test_repo", "test_dept", False)
        >>> r.add_auth('/test1', 'test_user1', Auth.READ_WRITE)
        >>> r.users()
        ['test_user1']
        >>> r.add_auth('/test1', 'test_user2', Auth.READ_WRITE)
        >>> r.users()
        ['test_user1', 'test_user2']

        """
        users = sets.Set()

        group_members = itertools.chain(*[ g.members for g in self.groups ])
        for user in itertools.chain(group_members,
                                    [ a.user for a in self.authorizations ]):
            if user.startswith('@') or user in config.NON_LDAP_USERS:
                continue
            users.add(user)


        users = list(users)
        users.sort()
        return users

    def write_authz(self):
        open(self.apache_authz, 'w').write(self.authz())


class Group (object):
    """A group of repository users."""

    def __init__(self, name, members=[]):
        """

        >>> g = Group('empty')
        >>> g.name
        'empty'
        >>> g.members
        []
        >>> g = Group('not empty', ['foo', 'bar'])
        >>> g.name
        'not empty'
        >>> g.members
        ['foo', 'bar']

        """
        self.name = name
        self.members = members[:]

    def add(self, member):
        """
        Add a group member.

        >>> g = Group('test')
        >>> g.add('foo')
        >>> g.members
        ['foo']

        """
        if not member in self.members:
            self.members.append(member)
        else:
            raise ValueError("%s is already a member of %s" % (member,
                                                               self.name))

    def remove(self, member):
        """
        Remove a group member.

        >>> g = Group('test', ['foo', 'bar'])
        >>> g.remove('foo')
        >>> g.members
        ['bar']

        """
        try:
            self.members.remove(member)
        except ValueError:
            raise ValueError("%s is not a member of the %s group" % (member,
                                                                     self.name))
    def __iter__(self):
        return iter(self.members)

    def __repr__(self):
        return "Group(%s, %s)" % (self.name, self.members)


class Auth (object):
    READ_ONLY = 'r'
    READ_WRITE = 'rw'
    MODES = (READ_ONLY, READ_WRITE)

    def __init__(self, path, user, mode):
        self.path = path
        self.user = user
        self.mode = mode

        if not self.path.startswith('/'):
            raise ValueError("Invalid path: %s." % self.path)

        if not self.mode in self.MODES:
            raise ValueError("Invalid mode: %s." % self.mode)

    def __repr__(self):
        return "Auth(%s, %s, %s)" % (self. path, self.user, self.mode)


    def __cmp__(self, other):
        if not other:
            return 1
        """ Set comparison rules for sorting Auth objects
            Paths are sorted alphabetically. Shorter paths are higher precidence
            Modes 'r', or 'rw' are sorted alphabetically.
            If path and mode e equal, sort by user alphabetically
            r is listed before rw (more restrictive)
            >>> a = Auth( '/', 'esf221', 'rw')
            >>> b = Auth( '/eeee', 'esf221', 'rw')
            >>> c = Auth( '/', 'esf221', 'r')
            >>> as = [c,a,b]
            >>> as.sort()
            >>> as
            [Auth(/, esf221, r), Auth(/, esf221, rw), Auth(/eeee, esf221, rw)]
        """
        pc = cmp(self.path, other.path)
        if pc: return pc

        mc = cmp(self.mode, other.mode)
        if mc: return mc

        return cmp(self.user, other.user)

def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()
