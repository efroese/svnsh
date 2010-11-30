import cmd
import sys
import shlex
import new

import repopy.command
from repopy.command import CommandArgumentError, CommandOptionError, CommandError


try:
    import readline
except:
    pass


def _make_do_cmd(command):
    def do_cmd(self, line):
        args = shlex.split(line)
        try:
            command(args)
        except (CommandArgumentError, CommandOptionError), e:
            print e
            print command.usage
        except CommandError, e:
            print e

    return do_cmd

def _make_help_cmd(command):
    def help_cmd(self):
        command.help()

    return help_cmd

class Shell(cmd.Cmd):

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = '>>> '

        self.names = []

        for name in repopy.command.__all__:
            command = getattr(repopy.command, name)
            self.add_command(command)


    def emptyline(self):
        """Ignore empty lines."""
        pass


    def do_exit(self, arg):
        sys.exit(0)


    def help_exit(self):
        print "exit: exit the shell"

    do_EOF = do_exit

    def _add_command(self, name, fun):
        cmd = new.instancemethod(fun,
                                 self,
                                 self.__class__)
        setattr(self, name, cmd)
        self.names.append(name)

    def add_command(self, command):
        do_name = 'do_%s' % command.name
        help_name = 'help_%s' % command.name
        self._add_command(do_name, _make_do_cmd(command))
        self._add_command(help_name, _make_help_cmd(command))


    _get_names = cmd.Cmd.get_names

    def get_names(self):
        names = self._get_names()
        return names + self.names


if __name__ == '__main__':
    shell = Shell()
    shell.cmdloop()
