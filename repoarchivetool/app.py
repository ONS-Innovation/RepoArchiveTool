import flask
from datetime import datetime
import os
import apiScript

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/', methods=['POST', 'GET'])
def index():
    if flask.request.method == "POST":
        flask.session['pat'] = flask.request.form['pat']

    try:
        with open("repositories.txt", "r") as f:
            repos = f.read().split(";")
            repos.pop()

            for i in range(0, len(repos)):
                name, url, lastCommit, dateAdded, keep = repos[i].split(",")
                repos[i] = {
                    "name": name,
                    "dateAdded": dateAdded,
                    "lastCommit": lastCommit,
                    "keep": keep
                }
    except FileNotFoundError:
        repos = ""

    try:
        return flask.render_template('index.html', pat=flask.session['pat'], date=datetime.now().strftime("%Y-%m-%d"), repos=repos)
    except KeyError:
        return flask.render_template('index.html', pat='', date=datetime.now().strftime("%Y-%m-%d"), repos=repos)

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
            try:
                return flask.render_template('error.html', pat=flask.session['pat'], error='Personal Access Token Undefined.')
            except KeyError:
                return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')
        
        else:
            # Get form values
            org = flask.request.form['org']
            date = flask.request.form['date']
            repoType = flask.request.form['repoType']

            repos = apiScript.GetOrgRepos(org, date, repoType, gh)

            if type(repos) == str:
                # Error Message Returned                
                try:
                    return flask.render_template('error.html', pat=flask.session['pat'], error=repos)
                except KeyError:
                    return flask.render_template('error.html', pat='', error=repos)

            with open("repositories.txt", "a+") as f:
                # Get current date for logging purposes
                currentDate = datetime.today().strftime("%Y-%m-%d")

                for repo in repos:
                    f.write(f"{repo['name']},{repo['apiUrl']},{repo['lastCommitDate']},{currentDate},0;")
                
            return flask.redirect('/')
            
            # Test to get repo owner email
            # need to make another api call to owner info and get it there
                
            # owner = gh.get("https://api.github.com/repos/ONS-Innovation/AI_Testing_App", {}, False).json()["owner"]["url"]
            # return gh.get(owner, {}, False).json()["email"]
    
    return flask.redirect('/')

@app.route('/clearRepositories')
def clearRepos():
    os.remove("repositories.txt")
    return flask.redirect('/')

if __name__ == "__main__":
    app.run(debug=True)