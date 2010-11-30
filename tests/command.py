import unittest
import operator

import repopy.command

class ArgumentCountTestCase(unittest.TestCase):

    def test_validate(self):
        count = repopy.command.ArgumentCount(2)
        self.failUnless(count.validate([1, 2]))
        self.failIf(count.validate([1]))

        count = repopy.command.ArgumentCount(2, operator.ge)
        self.failUnless(count.validate([1, 2]))
        self.failUnless(count.validate([1, 2, 3]))
        self.failIf(count.validate([1]))

