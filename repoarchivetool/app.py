import flask
from datetime import datetime, timedelta
import os
import json

import apiScript

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/', methods=['POST', 'GET'])
def index():
    if flask.request.method == "POST":
        flask.session['pat'] = flask.request.form['pat']

    try:
        return flask.render_template('index.html', pat=flask.session['pat'], date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
    except KeyError:
        return flask.render_template('index.html', pat='', date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))

@app.route('/login', methods=['POST', 'GET'])
def login():
    if flask.request.method == 'POST':
        flask.session['pat'] = flask.request.form['pat']

        # No need to test token here as tested when getting repos

        return flask.redirect('/')
    return flask.redirect('/')

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    flask.session.pop('pat', None)
    return flask.redirect('/')

@app.route('/FindRepositories', methods=['POST', 'GET'])
def findRepos():
    if flask.request.method == 'POST':
        try:
            # Create APIHandler instance
            gh = apiScript.APIHandler(flask.session['pat'])
        
        except KeyError:
            return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')
        
        else:
            # Get form values
            org = flask.request.form['org']
            date = flask.request.form['date']
            repoType = flask.request.form['repoType']

            newRepos = apiScript.GetOrgRepos(org, date, repoType, gh)

            if type(newRepos) == str:
                # Error Message Returned                
                try:
                    return flask.render_template('error.html', pat=flask.session['pat'], error=newRepos)
                except KeyError:
                    return flask.render_template('error.html', pat='', error=newRepos)

            # Get current date for logging purposes
            currentDate = datetime.today().strftime("%Y-%m-%d")

            reposAdded = 0

            # Get repos from storage
            try:
                with open("repositories.json", "r") as f:
                    storedRepos = json.load(f) 
            except FileNotFoundError:
                # File doesn't exist therefore no repos stored
                storedRepos = []

            for repo in newRepos:
                if not any(d["name"] == repo["name"] for d in storedRepos):
                    storedRepos.append({
                        "name": repo["name"],
                        "apiUrl": repo["apiUrl"],
                        "lastCommit": repo["lastCommitDate"],
                        "dateAdded": currentDate,
                        "keep": False
                    })

                    reposAdded += 1

            with open("repositories.json", "w") as f:
                f.write(json.dumps(storedRepos, indent=4))
                
            return flask.redirect(f'/manageRepositories?reposAdded={reposAdded}')
            
            # Test to get repo owner email
            # need to make another api call to owner info and get it there
                
            # owner = gh.get("https://api.github.com/repos/ONS-Innovation/AI_Testing_App", {}, False).json()["owner"]["url"]
            # return gh.get(owner, {}, False).json()["email"]
    
    return flask.redirect('/')

@app.route('/manageRepositories')
def manageRepos():

    # Get repos from storage
    try:
        with open("repositories.json", "r") as f:
            repos = json.load(f) 
            repos.sort(key=lambda x: x["name"])
    except FileNotFoundError:
        # File doesn't exist therefore no repos stored
        repos = []

    reposAdded = flask.request.args.get("reposAdded")

    if reposAdded == None:
        reposAdded = 0
    else:
        reposAdded = int(reposAdded)

    try:
        return flask.render_template('manageRepositories.html', pat=flask.session['pat'], repos=repos, reposAdded=reposAdded)
    except KeyError:
        return flask.render_template('manageRepositories.html', pat='', repos=repos, reposAdded=reposAdded)

@app.route('/clearRepositories')
def clearRepos():
    os.remove("repositories.txt")
    return flask.redirect('/manageRepositories')

@app.route('/changeKeepFlag')
def changeFlag():
    repoName = flask.request.args.get("repoName")

    if repoName == None:
        return flask.redirect('/manageRepositories')

    with open("repositories.json", "r") as f:
        repos = json.load(f)

    for i in range(0, len(repos)):
        if repoName == repos[i]["name"]:
            repos[i]["keep"] = not repos[i]["keep"]
            break

    with open("repositories.json", "w") as f:
        f.write(json.dumps(repos, indent=4))
        
    return flask.redirect('/manageRepositories')

@app.route('/archiveRepositories', methods=['POST', 'GET'])
def archiveRepos():
    try:
        gh = apiScript.APIHandler(flask.session['pat'])
    except KeyError:
        return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')

    # A list of dictionaries to keep track of what repos have been archived (w/ success status)
    archiveList = []

    with open("repositories.json", "r") as f:
        repos = json.load(f)

    for repo in repos:
        if not repo["keep"]:
            if (datetime.now() - datetime.strptime(repo["dateAdded"], "%Y-%m-%d")).days >= 30:
                response = gh.patch(repo["apiUrl"], {"archived":True}, False)

                if response.status_code == 200:

                    archiveList.append({
                        "name": repo["name"],
                        "apiurl": repo["apiUrl"],
                        "status": "Success",
                        "message": "Repository Archived Successfully."
                    })

                else:
                    archiveList.append({
                        "name": repo["name"],
                        "apiurl": repo["apiUrl"],
                        "status": "Failed",
                        "message": f"Error {response.status_code}: {response.json()["message"]}"
                    })

    return archiveList

    # Need to write archiveList to JSON then redirect to /recentlyArchived

@app.route('/recentlyArchived')
def recentlyArchived():
    try:
        return flask.render_template('recentlyArchived.html', pat=flask.session['pat'])
    except KeyError:
        return flask.render_template('recentlyArchived.html', pat='')

if __name__ == "__main__":
    app.run(debug=True)