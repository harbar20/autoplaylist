#Written by Luke Carapezza (@lukec11), December 2019

import sys
import spotipy
import spotipy.util
import json
from flask import Flask, request, abort, Response
import jsonify


#imports methods from main
from main import interpret_song, slack_ephemeral


import traceback
from werkzeug.wsgi import ClosingIterator

class AfterResponse: 
    def __init__(self, app=None):
        self.callbacks = []
        if app:
            self.init_app(app)

    def __call__(self, callback):
        self.callbacks.append(callback)
        return callback

    def init_app(self, app):
        # install extension
        app.after_response = self

        # install middleware
        app.wsgi_app = AfterResponseMiddleware(app.wsgi_app, self)

    def flush(self):
        for fn in self.callbacks:
            try:
                fn()
            except Exception:
                traceback.print_exc()

class AfterResponseMiddleware: # credit Matthew Story @ Stackoverflow
    def __init__(self, application, after_response_ext):
        self.application = application
        self.after_response_ext = after_response_ext

    def __call__(self, environ, after_response):
        iterator = self.application(environ, after_response)
        try:
            return ClosingIterator(iterator, [self.after_response_ext.flush])
        except Exception:
            traceback.print_exc()
            return iterator



with open("config/SPconfig.json") as f:
    spotifyConfig = json.load(f)
    
    spotifyClientId = spotifyConfig["clientID"]
    spotifyClientSecret = spotifyConfig["clientSecret"]
    spotifyBearer = spotifyConfig["bearer"]
    spotifyPlaylistId = spotifyConfig["playlistID"]
    spotifyCtr = spotifyConfig["ctr"]
    spotifyUser = spotifyConfig["spotifyUser"]
    
with open ("config/slack.json") as f:
    slackConfig = json.load(f)
    
    slackTeamId = slackConfig["team"]
    slackToken = slackConfig["verificationToken"]

def searchSpotify(vquery):
    
    #global vars
    global username
    
    
    query = [vquery] #This converts the UID string into a list, because spotipy api only accepts inputs as lists.
    
    scope = 'playlist-modify-public' #Describes the scope necessary, so spotify API can authorize.

    if (len(sys.argv) > 1): #stuff that spotipy uses - leaving it here so stuff doesn't break
        username = sys.argv[1]
    else:
        ("Usage: {} username".format(sys.argv[0])) #This is entirely irrelevant, but the code doesn't run without it.

    token = spotipy.util.prompt_for_user_token(spotifyUser, #prompts for spotify user token, so it can access the api
                                               scope,
                                               client_id=spotifyClientId,
                                               client_secret=spotifyClientSecret,
                                               redirect_uri='http://localhost:9898/spotifyCallback'
                                               ) #Authorizes with Spotify using OAuth

    
    sp = spotipy.Spotify(auth=token)
    sp.trace = False #idk what this does but the docs told me to do it
    
    try:
        tracks = sp.search(query, limit=1, offset=0, type="track", market=None)
        tracks2 = tracks.get('tracks').get('items')[0].get('uri')
        return tracks2
    except (IndexError or AttributeError):
        slack_ephemeral('We couldn\'t find this track! Try searching in a different format, e.g. "artist - title"', username) #returns ephemeral message to user
        print ("Served response: NOT FOUND") #logs output to console for debug
        return "NotFound"


#flask stuff to accept slack slash commands
app = Flask("after_response")
AfterResponse(app) #calls AfterResponse after flask app

username = "" #initializes to blank by default
text = ""

def request_valid(request):
    slackToken = request.form['token']
    #slackTeamId = request.form['team-id']
    return slackToken

@app.after_response
def after_request_function():
    
    #global vars
    global username
    global text
    
    #code doesn't work without this for some reason
    song = str(text)
    
    print(f"User {username} requested the song \"{song}\".") #prints request to console
        
    #runs interpretation with info from spotify - will serve final message there
    interpret_song(searchSpotify(song), username, 'cmd') 


@app.route('/songadd', methods=['POST'])
def songadd():
    if not request_valid(request):
        print ('NOT VALID!')
        abort(400)
    
    
    #global vars
    global username
    global text
    
    #gets vars based on slack's post
    username = request.form.get('user_id')
    text = request.form.get('text')
    
  
    
    return Response("Your songs are on their way! Please give us a moment.") #returns early response, because slack needs a response within a few minutes to work properly
  



#flask stuff that runs web server
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=8043) #turn off debug before running in prod
    