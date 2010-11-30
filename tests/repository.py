import unittest

import repopy.repository
from repopy.repository import Auth


class RemoveAuthTestCase(unittest.TestCase):

    def setUp(self):
        self.repo = repopy.repository.Repository('bar', 'foo')
        self.repo.add_auth('/foo', 'neil', Auth.READ_WRITE)
        self.repo.add_auth('/foo', 'neil', Auth.READ_ONLY)

    def test_duplicate_auths_empty(self):
        self.repo.remove_auth('/foo', 'neil')
        self.assertEqual(self.repo.authorizations, [])

    def test_duplicate_auths_non_empty(self):
        self.repo.add_auth('/foo', 'bob', Auth.READ_ONLY)
        self.repo.remove_auth('/foo', 'neil')
        self.assertEqual(len(self.repo.authorizations), 1)
        auth = self.repo.authorizations[0]
        self.assertEqual(auth.user, 'bob')
        self.assertEqual(auth.path, '/foo')

