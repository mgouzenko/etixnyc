#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import webapp2
import os
import jinja2
from google.appengine.ext import db
import urllib2 as url
import json
import logging
import datetime
import httplib2
import restclient



template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)


class Handler(webapp2.RequestHandler):

    header_file = open(os.path.join("templates", "header"))
    header = header_file.read()

    footer_file = open(os.path.join("templates", "footer"))
    footer = footer_file.read()

    searchbar_file = open(os.path.join("templates", "searchbar"))
    searchbar = searchbar_file.read()

    form_file = open(os.path.join("templates", "review_form.html"))
    form = form_file.read()

    def render_toolbar(self, **params):
        toolbar = jinja_env.get_template("toolbar")
        toolbar = toolbar.render(params)
        return toolbar

    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    #grabs the desired template from the templates folder and renders it w/jinja syntax as per the parameters passed in
    #returns the html with all {{}} statements evaluated
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    #writes the above returned html template to the webpage
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def render_form(self, time="", honesty="", reliability="", error="", com=""):
        self.render("review_form.html", header=self.header,
                    footer=self.footer, time=time, honesty=honesty,
                    reliability=reliability, error=error, com=com)

    def validate_cookies(self, request):
        '''Checks if a user's access token is valid. If valid, sets cookies for name, username, and id.'''
        access_token = request.cookies.get('access_token')
        user_id = request.cookies.get('user_id')
        if access_token and user_id:
            request_string = "https://graph.facebook.com/"+user_id+"?access_token="+access_token
            #self.write(request_string)
        else:
            self.redirect("/login")
        try:
            p = url.urlopen(request_string)
            c = p.read()
            j = json.loads(c)
            if "id" in j and "name" in j:
                if not("username" in j):
                    j["username"] = j["id"]
                return j
            else:
                self.redirect("/login")
        except:
            self.redirect("/login")

    def get_reviews(self, userid, *args):
        if 'reviewer' in args:
            id_search = db.GqlQuery("SELECT * FROM Reviews WHERE reviewer_id= :str order by created desc", str=userid)
        elif 'arbitrary' in args:
            id_search = db.GqlQuery("SELECT * FROM Reviews order by created desc")
        else:
            id_search = db.GqlQuery("SELECT * FROM Reviews WHERE reviewed_id= :str order by created desc", str=userid)
        reviews = []
        for review in id_search:
            dict={}
            dict['reviewer_id'] = str(review.reviewer_id)
            dict['timeliness'] = str(review.timeliness)
            dict['reliability'] = str(review.reliability)
            dict['honesty'] = str(review.honesty)
            dict['com'] = str(review.com)
            created = review.created.date()
            dict['created'] = created
            dict['reviewer_name'] = str(review.reviewer_name)
            dict['reviewed_name'] = str(review.reviewed_name)
            dict['reviewed_id'] = str(review.reviewed_id)
            reviews.append(dict)
        return reviews

    def set_identifying_cookies(self, j):
        if "first_name" in j:
            self.response.headers.add_header('Set-Cookie', 'first_name=%s' % str(j["first_name"]))
        if "last_name" in j:
            self.response.headers.add_header('Set-Cookie', 'last_name=%s' % str(j["last_name"]))
        if "username" in j:
            self.response.headers.add_header('Set-Cookie', 'username=%s' % str(j["username"]))

    def get_user_data(self, username):
        try:
            request_string = "https://graph.facebook.com/"+username+"?access_token=538470186266511|a0a13df49f083533966b7eca59b3d8b7"
            hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
           'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
           'Accept-Encoding': 'none',
           'Accept-Language': 'en-US,en;q=0.8',
           'Connection': 'keep-alive'}

            req = url.Request(request_string, headers=hdr)
            p = url.urlopen(req)
            c = p.read()
            j = json.loads(c)
            if j:
                userid = str(j["id"]).lower()
                try:
                    name = str(j["name"]).lower()
                    fname = name.split()[0].capitalize()
                    lname = name.split()[1].capitalize()
                    name = fname+" "+lname
                except:
                    name = "NULL"
                try:
                    username = str(j["username"]).lower()
                except:
                    username = userid
                l = {'userid': userid, 'name': name, 'username': username}
                return l
        except url.HTTPError, e:
            self.write(e.fp.read())
            self.write(username)
            self.write(request_string)
            return {'userid': "null", 'name': "null", 'username': "null"}

    def average_ratings(self, reviews):
        time = 0.
        honesty = 0.
        reliability = 0.
        for review in reviews:
            time += int(review['timeliness'])
            honesty += int(review['honesty'])
            reliability += int(review['reliability'])
        if len(reviews)!=0:
            time = int((time/len(reviews)*25))
            honesty = int((honesty/len(reviews))*25)
            reliability = int((reliability/len(reviews))*25)
        else:
            time = 'None'
            honesty = 'None'
            reliability = 'None'

        return {'timeliness': str(time), 'honesty': str(honesty), 'reliability': str(reliability)}



    def scrape_user_data(self, usrobj):
        ident = usrobj["id"]
        current_instance = db.GqlQuery("SELECT * FROM Users WHERE id= :str", str=ident)
        key = False
        date = datetime.datetime(2013,1,1)
        if len(list(current_instance)) != 0:
            key = current_instance[0].key()
            date = current_instance[0].friends_scraped
        for i in Users.properties():
            if not(i in usrobj):
                usrobj[i] = None
        logging.info("Last friend scrape:" + str(date) + ", source: main.scrape_user_data")
        user = Users(id=str(usrobj["id"]).lower(),
                     name=str(usrobj["name"]).lower(),
                     first_name=str(usrobj["first_name"]).lower(),
                     last_name=str(usrobj["last_name"]).lower(),
                     work=str(usrobj["work"]).lower(),
                     education=str(usrobj["education"]).lower(),
                     gender=str(usrobj["gender"]).lower(),
                     timezone=usrobj["timezone"],
                     username=str(usrobj["username"]).lower(),
                     friends_scraped = date,
                     )
        if user:
            user.put()
            if key:
                db.delete(key)


class UserProfile(Handler):
    def get(self):
        if self.validate_cookies(self.request):
            #make toolbar
            name = self.request.cookies.get("first_name") + " "
            name += self.request.cookies.get("last_name")
            toolbar = self.render_toolbar(name=name)

            #figure out what the query is and if we should display a thanks message
            thanks = str(self.request.get("thanks"))
            query = str(self.request.get("query"))

            username = query.strip("/")
            query = query.split("/")
            reviews = self.get_reviews(123, 'arbitrary')
            reviews = reviews[0:8]
            does_query_exist = False
            ratings = {'exist': False}
            user_dict = {}
            if query:
                for i in range(len(query)-1):
                    if query[i] in ('www.facebook.com', 'facebook.com', 'facebook'):
                        query = query[i+1]
                        query = query.split("?")
                        #will set the username if query was in the form of url
                        username = query[0]
                        if username == 'profile.php':
                            username = query[1]
                            username = username.split('&')
                            username = username[0].split('=')[1]
                if username:
                    user_dict = self.get_user_data(username)
                    reviewed_id="NULL"
                    my_username=self.request.cookies.get("username")
                    my_dict=self.get_user_data(my_username)
                    my_id = my_dict['userid']
                    if 'userid' in user_dict:
                        reviewed_id = str(user_dict['userid'])
                    if username == my_username or username==my_id:
                        self.redirect("/profile")
                    reviews = self.get_reviews(reviewed_id)
                    does_query_exist = True
                    ratings = self.average_ratings(reviews)
                    ratings['exist']=True

            self.render("user.html",
                        searchbar=self.searchbar,
                        header=self.header,
                        footer=self.footer,
                        toolbar=toolbar,
                        user_dict=user_dict,
                        thanks=thanks,
                        form=self.form,
                        reviews=reviews,
                        ratings=ratings,
                        page="1",
                        does_query_exist=does_query_exist)
        else:
            self.redirect("/")


class Home(Handler):
    def get(self):
        if self.validate_cookies(self.request):
            #make toolbar
            name=""
            try:
                name = self.request.cookies.get("first_name") + " "
                name += self.request.cookies.get("last_name")
            except:
                self.redirect('/login')
            toolbar = self.render_toolbar(name=name)
            reviews = self.get_reviews(123, 'arbitrary')
            reviews = reviews[0:8]
            self.render("home.html",
                        searchbar=self.searchbar,
                        header=self.header,
                        footer=self.footer,
                        toolbar=toolbar,
                        form=self.form,
                        reviews=reviews, page="1")
        else:
            self.redirect("/")


class MainPage(Handler):
    def get(self):
        user_info = self.validate_cookies(self.request)
        log = self.request.cookies.get("has_just_logged")
        if user_info:
            #if the user has just logged in
            if log == 'True':
                self.response.headers.add_header('Set-Cookie', 'has_just_logged=False')
                self.set_identifying_cookies(user_info)
                self.scrape_user_data(user_info)
                access_token = self.request.cookies.get('access_token')
                user_id = self.request.cookies.get('user_id')
                friend_scrape_request = 'http://localhost:8080/scrape?token=' + access_token + '&id=' + user_id
                restclient.GET(friend_scrape_request, async=True)
                self.redirect("/home")
            else:
                self.redirect("/home")
        else:
            self.redirect("/login")


class FormHandler(Handler):
    def post(self):
        reviewer = self.validate_cookies(self.request)
        if reviewer:
            time = int(self.request.get("timeliness"))
            rel = int(self.request.get("reliability"))
            honesty = int(self.request.get("honesty"))
            com = str(self.request.get("com"))
            reviewer_id = self.request.cookies.get("user_id")
            reviewer_name = reviewer["name"]
            reviewed_id = str(self.request.get("userid"))
            reviewed_name = str(self.request.get("reviewed_name"))
            buyer = "True"
            #delete all other entries with same review_id
            entries = db.GqlQuery("SELECT * FROM Reviews Where reviewer_id = :str and reviewed_id = :str2", str=reviewer_id, str2=reviewed_id)
            for entry in entries:
                db.delete(entry)
            review = Reviews(timeliness=time, reliability=rel, honesty=honesty,
                             com=com, reviewer_id=reviewer_id, reviewed_id=reviewed_id, reviewed_name=reviewed_name,
                             reviewer_name=reviewer_name, buyer=buyer)
            review.put()
            self.redirect("/user?thanks=true&query=%s" % reviewed_id)
        else:
            self.redirect("/")


class Login(Handler):
    def get(self):
        self.render("login.html", header=self.header, footer=self.footer)


class Logout(Handler):
    def get(self):
        self.render("logout.html", header=self.header, footer=self.footer)

class Profile(Handler):
    def get(self):
        user = self.validate_cookies(self.request)
        if user:
            try:
                l = self.get_user_data(user['username'])
            except:
                l = self.get_user_data(user['id'])
            reviews=[]
            name = self.request.cookies.get("first_name") + " "
            name += self.request.cookies.get("last_name")
            toolbar = self.render_toolbar(name=name)
            reviews = self.get_reviews(user['id'])
            my_reviews = self.get_reviews(self.request.cookies.get("user_id"), 'reviewer')
            #self.write(my_reviews)
            ratings = self.average_ratings(reviews)
            if ratings["timeliness"] == "None":
                ratings['exist'] = False
            else:
                ratings['exist'] = True
            self.render("profile.html",
                        header=self.header,
                        footer=self.footer,
                        toolbar=toolbar,
                        user_dict=l,
                        form=self.form,
                        reviews=reviews,
                        my_reviews=my_reviews,
                        page="1",
                        ratings=ratings)


class Contact(Handler):
    def get(self):
        name = self.request.cookies.get("first_name") + " "
        name += self.request.cookies.get("last_name")
        toolbar = self.render_toolbar(name=name)
        self.render("contact.html", header=self.header, footer=self.footer, toolbar=toolbar)


class ScrapeFriends(Handler):
    def get(self):
        token = self.request.get("token")
        id = self.request.get("id")
        id_search = db.GqlQuery("SELECT * FROM Reviews WHERE reviewer_id= :str order by created desc", str=id)
        last_scraped = datetime.datetime(2013,1,1)
        old_entry = ""
        for person in id_search:
            last_scraped = person.friends_scraped
            key = person.key
            old_entry=person
        now = datetime.datetime.now()
        timedelta = now - last_scraped
        if timedelta.total_seconds() > 259200:
            request_string = 'https://graph.facebook.com/' + id + '/friends?access_token=' + token
            logging.info(request_string)
            request = url.urlopen(request_string)
            request = request.read()
            json_obj = json.loads(request)
            while len(json_obj['data']) > 0:
                friendlist = json_obj['data']
                for friend in friendlist:
                    entry = SearchBase(id=friend['id'],
                                       name = friend['name']
                                       )
                    if entry:
                        entry.put()
                next_pg = json_obj["paging"]["next"]
                logging.info("next page:" + next_pg)
                new_request = url.urlopen(next_pg)
                new_request = new_request.read()
                logging.info(new_request)
                json_obj = json.loads(new_request)
            logging.info('Search base updated')
            #update friend scraped parameter
            new_entry = Users(id = old_entry.id,
                              name = old_entry.name,
                              first_name = old_entry.first_name,
                              last_name = old_entry.last_name,
                              work = old_entry.work,
                              education = old_entry.education,
                              gender = old_entry.gender,
                              timezone = old_entry.timezone,
                              username = old_entry.username,
                              friends_scraped = now,
                              )

            try:
                new_entry.put()
                db.delete(key)
            except:
                pass


        else:
            logging.info('Friends last scraped: ' + last_scraped)


class Faq(Handler):
    def get(self):
        name = self.request.cookies.get("first_name") + " "
        name += self.request.cookies.get("last_name")
        toolbar = self.render_toolbar(name=name)
        self.render("faq.html", header=self.header, footer=self.footer, toolbar=toolbar)

class Search(Handler):
    def get(self):
        access_token = self.request.cookies.get("access_token")
        self.write(access_token)
        '''
        query = self.request.get("q")
        self.write(query)
        usernames = resources.usernames.usernames()
        results = {}
        for person in usernames:
            personlist = person.split()
            for name in personlist:
                if name == query:
                    results[person] = usernames[person]
        self.write(results)
        '''


#####DATA STRUCTURES#####
class Reviews(db.Model):
    #general comments
    com = db.TextProperty(required=True)

    #Did you end up with a REAL ticket? If there was a problem with the ticket, did the seller refund you or did they change their name
    #and block you on facebook?
    honesty = db.IntegerProperty(required=True)

    #timeliness: was the person there when you expected, or did you have to wait for them? Did it take a long time for them
    #to respond to your texts?
    timeliness = db.IntegerProperty(required=True)

    #reliability: Did the user deliver the product as promised, or did they flake last minute? Did they charge you more
    #than the price they promised you?
    reliability = db.IntegerProperty(required=True)

    #buyer: Did you buy from or sell to this person?
    buyer = db.StringProperty()

    #Id of the reviewer
    reviewer_id = db.StringProperty(required=True)
    reviewer_name = db.StringProperty(required=True)

    #ID of the person being reviewed
    reviewed_id = db.StringProperty(required=True)
    reviewed_name = db.StringProperty(required=True)

    created = db.DateTimeProperty(auto_now_add=True)


class Users(db.Model):
    id = db.StringProperty()
    name = db.StringProperty()
    first_name = db.StringProperty()
    last_name = db.StringProperty()
    work = db.TextProperty()
    education = db.TextProperty()
    gender = db.StringProperty()
    timezone = db.IntegerProperty()
    username = db.StringProperty()
    friends_scraped = db.DateTimeProperty()
    created = db.DateTimeProperty(auto_now_add=True)


class SearchBase(db.Model):
    id = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/form_submit', FormHandler),
                               ('/login', Login),
                               ('/home', Home),
                               ('/logout', Logout),
                               ('/profile', Profile),
                               ('/contact', Contact),
                               ('/faq', Faq),
                               ('/user', UserProfile),
                               ('/search', Search),
                               ('/scrape', ScrapeFriends)
                               ], debug=True)  # REMEMBER TO ADD YOUR FUCKING COMMAS





