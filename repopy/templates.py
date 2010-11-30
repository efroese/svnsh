
import os
import repopy.config as config

class Template:
    """
    A very simple template class. Basically a wrapper around the
    printf style string substition.

    """

    def __init__(self, params, template=None, template_string=None):
        """
        Create a new template object.
        """
        self.file = template
        self.params = params
        self.template = None

        if template_string:
            self.template = template_string
        else:
            if not self.file.startswith(os.path.sep):
                self.file = os.path.join(config.TEMPLATE_DIR, self.file)
                #print self.file
            if not (os.path.exists(self.file) and os.path.isfile(self.file)):
                raise ValueError("Can't find template file for %s." % self.file)

    def process(self, data):
        """
        Process the template with the template parameters bound to the
        matching values of data dictionary. Returns the template
        output as a string.
        """
        if not self.template:
            fh = open(self.file, 'r')
            self.template = fh.read()
            fh.close()

        for param in self.params:
            if not data.has_key(param):
                raise ValueError("Missing required template parameter %s." % param)

        return self.template % data

    def process_to_file(self, filename, data):
        """
        Like process, but the processed template is written to
        filename.
        """
        f = file(filename, 'w')
        f.write(self.process(data))
        f.close()


apache_conf = Template(template='apache.conf',
                       params=['repopath', 'apache_authz_path'])
fisheye_conf = Template(template='fisheye.conf',
                        params=['repopath', 'users'])
fisheye_site_conf = Template(template='fisheye.site.conf',
                             params=['users'])

