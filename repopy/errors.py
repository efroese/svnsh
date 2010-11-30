# Error Classes

import exceptions

class CommandError(exceptions.Exception):
    def __str__(self):
        return "\n".join(self.args)


class CommandArgumentError(CommandError):
    pass


class CommandOptionError(CommandError):
    pass

class InvalidPasswordError(CommandError):
    pass
