import unittest
from tempfile import mktemp

import repopy.templates


class TemplateTestCase(unittest.TestCase):

    def test_process(self):
        template_string = """Foo: %(foo)s"""
        template = repopy.templates.Template(template_string=template_string,
                                             params=['foo'])
        processed = template.process({'foo': 'bar'})
        expected = "Foo: bar"
        self.assertEqual(processed, expected)
        self.assertRaises(ValueError, lambda d: template.process(d), {})

    def test_non_existing(self):
        non_existing_file = lambda: repopy.templates.Template(template=mktemp(),
                                                              params=[])
        self.assertRaises(ValueError, non_existing_file)


