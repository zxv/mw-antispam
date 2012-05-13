#!/home/private/.envs/antispam/bin/python
import requests, simplejson
import urllib, datetime, os
import pdb

QUERY_LIMIT = "400"
USER_WHITELIST = ["Despaminator"] # YMMV
DONE_FILE = "done.txt"
EARLIEST_DATE = datetime.datetime(2012, 4, 4) 

WIKI_PARAMS = {
    "site": "", # Wiki url goes here
    "format": "json", 
    "api_script": "api.php",
    "username": "Despaminator",
    "password": "",
}


class Wiki(object):
    def __init__(self, **kwargs):
        self.site = kwargs['site']
        self.format = kwargs['format']
        self.api_script = kwargs['api_script']
        self.article_list = []
        self.done_list = []
        self.unique_users = []

        # Initialize HTTP output stack
        self.stack = {}

        # Authenticate on mediawiki
        self.login(username=kwargs["username"], password=kwargs["password"])

        # Import done changes
        self.import_done()

    def generate_url(self):
        return "{0}/{1}".format(self.site, self.api_script)

    def list_params(self, **params):
        params['format'] = self.format
        params_formatted = ""
        query_sep = "?"

        for key in params:
            params_formatted = params_formatted + "{0}{1}={2}".format(query_sep, key, params[key])

            if query_sep == "?":
                query_sep = "&"

        return params_formatted

    def action_url(self, name, **params):
        params['action'] = name
        return "{0}".format(self.generate_url() + self.list_params(**params))

    def login(self, **kwargs):
        post_params = {"lgname": kwargs['username'], "lgpassword": kwargs['password']}
        login_args = self.action_url("login")

        # 1st step of login, generate token
        self.request = requests.post(login_args, data=post_params)
        processed = simplejson.loads(self.request.content)
        self.stack.update(processed)

        # POST cookie and updated params with auth token, log in
        post_params['lgtoken'] = self.stack['login']['token']
        login_args = self.action_url("login")
        self.cookies = self.request.cookies
        self.request = requests.post(login_args, cookies=self.cookies, data=post_params)

    def wikidate_to_datetime(self, indate):
        outdate = datetime.datetime.strptime(indate, '%Y-%m-%dT%H:%M:%SZ')
        return outdate 

    def filter_whitelist(self, users):
        # Only include changes made by non-whitelisted users
        self.change_list[:] = [change for change in self.change_list if change['user'] not in users]

    def filter_afterdate(self, date):
        # Only include changes made after date
        self.change_list[:] = [change for change in self.change_list if self.wikidate_to_datetime(change['timestamp']) > date]

    def get_changes(self, **kwargs):
        query_params = {
            "list": "recentchanges",
            "rclimit": str(QUERY_LIMIT),
            "rcprop": "user|timestamp|title|comment|flags|ids",
            "intoken": "edit",
        }
        self.request = requests.post(self.action_url("query", **query_params), cookies=self.cookies)
        self.change_list = simplejson.loads(self.request.content)['query']['recentchanges']

        self.filter_whitelist(USER_WHITELIST)
        self.filter_afterdate(EARLIEST_DATE)
        #self.getarticles()

    def get_articles(self, **kwargs):
        ''' Not used for now '''
        self.revert_list = list(set([change['title'] for change in self.change_list]))

    #def getearliestrevid(self,

    def reverse_spam(self):
        #for change in self.change_list:
        #    print "Undo: [[{0}]] ({1})".format(change['title'], change['comment'])
        for change in self.change_list:
            if str(change) not in self.done_list:
                if change['type'] == 'edit':
                    pass
                    #self.undo(change)
                elif change['type'] == 'new':
                    self.delete(change)

                # Assuming success, add to ignore list
                self.mark_as_done(change)
            else:
                pass
                #print "Duplicate detected, ignoring {0}".format(str(change))

    def find_unique_users(self):
        # Iterate over changes to identify unique users
        users = []
        for change in self.change_list:
            users.append(change['user'])
        self.unique_users = list(set(users))

    def block_users(self):
        for user in self.unique_users:
            self.blockuser(user)

    def delete(self, change):
        query_params = {
            "prop": "revisions|info",
            "intoken": "delete",
            "titles": change['title'],
        }

        # First, obtain delete token
        self.request = requests.post(self.action_url("query", **query_params), cookies=self.cookies)
        self.stack.update(simplejson.loads(self.request.content))
        delete_token = urllib.quote_plus(self.stack['query']['pages'].values()[0]['deletetoken'])

        delete_params = {
            "title": change['title'],
            "reason": "Delete spam page by [[User:{0}]]".format(change['user']),
            "token": delete_token,
        }
        self.request = requests.post(self.action_url("delete", **delete_params), cookies=self.cookies)

    def blockuser(self, user):
        pass

    def undo(self, change):
        query_params = {
            "prop": "revisions|info",
            "intoken": "edit",
            "titles": change['title'],
        }

        # First, obtain edit token
        self.request = requests.post(self.action_url("query", **query_params), cookies=self.cookies)
        self.stack.update(simplejson.loads(self.request.content))
        edit_token = urllib.quote_plus(self.stack['query']['pages'].values()[0]['edittoken'])

        undo_params = {
            "title": change['title'],
            "summary": "Undo spam edit by [[User:{0}]]".format(change['user']),
            "undo": change['revid'],
            "token": edit_token,
        }
        self.request = requests.post(self.action_url("edit", **undo_params), cookies=self.cookies)

    def mark_as_done(self, change):
        with open(DONE_FILE, "a") as f:
            f.write('\n' + str(change))
        
    def import_done(self):
        ''' This is a very fragile way of checking for completed reversions,
        because the moment that the order of any items in the dict change
        (or more are added), the checking mechanism breaks.'''

        # Create "done" file if it doesn't exist
        if not os.path.exists(DONE_FILE):
            file(DONE_FILE, 'w').close()

        # Open for reading and writing
        with open(DONE_FILE, "r") as f:
            for line in f:
                self.done_list.append(line.rstrip("\n"))

wiki = Wiki(**WIKI_PARAMS)
wiki.get_changes()
wiki.find_unique_users()
wiki.reverse_spam()
#wiki.block_users()
pdb.set_trace()
