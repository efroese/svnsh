# python std libs
import re
from urllib2 import HTTPError

# 3rd party libs
from BeautifulSoup import BeautifulSoup
from mechanize import Browser

# repopy
from config import FISHEYE_ADMIN_URL, REPO_ROOT
from errors import InvalidPasswordError


class FisheyeAdmin(object):
    """
        Performs actions on fisheye admin on your behalf.
    """
    def __init__(self, password=None):
        self.browser = Browser()
        self.password = password
        if self.password:
            if not self.login(self.password):
                raise InvalidPasswordError("Invalid fisheye admin password.")


    def login(self, admin_password=None):
        """
            Log into the fisheye admin.
            The login info is saved in a cookie by self.browser
        """
        admin_login_url = FISHEYE_ADMIN_URL + '/login.do'

        if not admin_password:
            admin_password = self.password

        try:
            self.browser.open(admin_login_url)
            self.browser.select_form(name='loginform')
            self.browser["adminPassword"] = admin_password
            try:
                self.browser.submit()
            except HTTPError, e:
                raise Exception("Unable to post to admin login form : " + str(e))
        except HTTPError, e:
            raise Exception("Unable to open the fisheye admin login page : " + str(e))

        # Got kicked back to the admin login page
        if self.browser.geturl() == FISHEYE_ADMIN_URL + '/login.do':
            self.logged_in = False
            raise InvalidPasswordError("Invalid fisheye admin password.")
        # Made it to the admin repo list
        elif self.browser.geturl() == FISHEYE_ADMIN_URL + '/viewRepList.do':
            self.logged_in = True
        # wtf?
        else:
            self.logged_in = False

        return self.logged_in


    def create_repository(self, repo, description):
        """
            Add a repository to fisheye.
        """

        if not self.logged_in:
            return False

        add_repo_url = FISHEYE_ADMIN_URL + '/addRep!default.do'
        try:
            self.browser.open(add_repo_url)

            self.browser.select_form(nr=0)
            self.browser['repository.name'] = repo.fisheye_name
            self.browser['repository.description'] = description
            self.browser['repoTypeSelection'] = ['SVN']
            self.browser['svn.url'] = 'file://%s' % repo.path_to_repo
            self.browser['svnSymbolic.type'] = ['none']

            try:
                self.browser.submit()
                result_url = self.browser.geturl().split('?')[0]
                if result_url == FISHEYE_ADMIN_URL + '/viewRep.do':
                    return True
                elif result_url == FISHEYE_ADMIN_URL + '/addRep.do':
                    return False
            except HTTPError, e:
                raise Exception("Unable to post to create repo form : " + str(e))
        except HTTPError, e:
            raise Exception("Unable to open the fisheye create repo page : " + str(e))


    def delete_repository(self, repo):
        """
            Delete a repository from fisheye.

            Open the repo list and figure out the repo id by parsing the page
            Click the link to stop repo
            Click the delete link
            Click the delete button on the subsequent form
        """
        if not self.logged_in:
            return False

        fisheye_repo_id = -1
        try:
            # Open the repository list
            viewrep = self.browser.open(FISHEYE_ADMIN_URL + '/viewRepList.do')
            soup = BeautifulSoup(viewrep.read())
            # Find the list of repos on the left side
            helpPane = soup.find("div", {"class" : "helpPane"})
            links = helpPane("ul")[2]("a")
            # Filter the links looking for the repo name (dept_name)
            links = filter(lambda l: l.contents[0] == repo.fisheye_name, links)
            if len(links) > 0:
                link = links[0]
            else:
                return False
            #Get the id out of there
            fisheye_repo_id = int(link["href"].split("=")[1])
        except HTTPError, e:
            raise Exception("Unable to open the admin repo list page : " + str(e))
        except ValueError, e:
            raise Exception("Error parsing the page to find the repo id : " + str(e))

        try:
            stop_url = '/manageRep.do?rep=%d&doStop=true' % fisheye_repo_id
            stop_url = FISHEYE_ADMIN_URL + stop_url
            self.browser.open(stop_url)

            delete_url = '/deleteRep!default.do?rep=%d' % fisheye_repo_id
            delete_url = FISHEYE_ADMIN_URL + delete_url
            self.browser.open(delete_url)

            self.browser.select_form(nr=0)
            self.browser.submit()
            return True
        except HTTPError, e:
            raise Exception("Unable to delete the repo. : " + str(e))


if __name__ == "__main__":
    pass
    # from getpass import getpass
    #     password = getpass('Fisheye admin pw : ')
    #
    #     fisheye = FisheyeAdmin()
    #     fisheye.login(password)
    #     fisheye.add_repository("testy", "its", "A test!")
    #     fisheye.delete_repository(name="testy", department="its")

