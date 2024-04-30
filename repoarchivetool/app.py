import flask
from datetime import datetime, timedelta, date
import os
from dateutil.relativedelta import relativedelta

import api_interface
import storage_interface

archive_threshold_days = 30
domain = "http://localhost:5000"

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.before_request
def check_pat():
    """
        Before any request, check if Personal Access Token is defined.
        If it's not, return a render of accessToken.html
    """
    if "pat" not in flask.session and flask.request.endpoint not in ("login", "set_exempt_date", "success"):
        return flask.render_template('accessToken.html')

@app.route('/', methods=['POST', 'GET'])
def index():
    """
        Returns a render of index.html.
    """

    return flask.render_template('findRepositories.html', date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))

@app.route('/login', methods=['POST', 'GET'])
def login():
    """
        Registers the user's inputted personal access token for Github Authentication.

        ==========

        When posted to, the function will set the session variable, pat, to the posted value.
        The session variable is intended to hold the user's personal access token for Github API authentication.

        Returns a redirect back to the homepage.
    """
    if flask.request.method == 'POST':
        flask.session['pat'] = flask.request.form['pat']

        # No need to test token here as tested when getting repos

    return flask.redirect('/')

@app.route('/logout')
def logout():
    """
        Removes the user's personal access token.
        
        ==========
        
        Unsets the session variable, pat, which holds the user's personal access token.

        Returns a redirect back to the homepage.
    """
    # remove the username from the session if it's there
    flask.session.pop('pat', None)
    return flask.redirect('/')

@app.route('/success')
def success():
    return flask.render_template("success.html")

@app.route('/find_repositories', methods=['POST', 'GET'])
def find_repos():
    """
        Gets and stores any Github repositories, using api_controller.py, which fits the given parameters.
        
        ==========
        
        When posted to, the function will use the inputted values from the homepage to make
        a request to the Github API using api_controller.py and its APIHandler class.
        The request will return any repositories which fit the inputted parameters, in which
        this function will store ANY NEW repositories in JSON (repositories.json).

        If this function is not posted to, it will return a redirect to the homepage.

        If the function receives an error after using api_controller.py, it will return a render of
        error.html with an appropriate error message.

        If the function is successful with obtaining the information, it will return a redirect to
        /manage_repositories with an in-URL arguement (reposAdded) which is used to display how many
        repositories are added to JSON.
    """
    if flask.request.method == 'POST':
        try:
            # Create APIHandler instance
            gh = api_interface.api_controller(flask.session['pat'])
        
        except KeyError:
            return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')
        
        else:
            # Get form values
            org = flask.request.form['org']
            date = flask.request.form['date']
            repo_type = flask.request.form['repoType']

            new_repos = api_interface.get_organisation_repos(org, date, repo_type, gh)

            if type(new_repos) == str:
                # Error Message Returned                
                try:
                    return flask.render_template('error.html', pat=flask.session['pat'], error=new_repos)
                except KeyError:
                    return flask.render_template('error.html', pat='', error=new_repos)

            # Get current date for logging purposes
            current_date = datetime.today().strftime("%Y-%m-%d")

            repos_added = 0

            # Get repos from storage
            stored_repos = storage_interface.read_file("repositories.json")

            new_repos_to_archive = []

            for repo in new_repos:
                if not any(d["name"] == repo["name"] for d in stored_repos):
                    contributor_list = api_interface.get_repo_contributors(gh, repo["contributorsUrl"])

                    stored_repos.append({
                        "name": repo["name"],
                        "type": repo["type"],
                        "contributors": contributor_list,
                        "apiUrl": repo["apiUrl"],
                        "lastCommit": repo["lastCommitDate"],
                        "dateAdded": current_date,
                        "exemptUntil": "1900-01-01",
                        "exemptReason": ""
                    })

                    new_repos_to_archive.append({
                        "name": repo["name"],
                        "url": repo["htmlUrl"]
                    })

                    repos_added += 1

            storage_interface.write_file("repositories.json", stored_repos)

            # Create html file to display which NEW repos will be archived
            with open("recentlyAdded.html", "w") as f:
                f.write("<h1>Repositories to be Archived</h1><ul>")
                for repo in new_repos_to_archive:
                    f.write(f"<li>{repo['name']} (<a href='{repo['url']}' target='_blank'>View Repository</a> - <a href='{domain}/set_exempt_date?repoName={repo['name']}' target='_blank'>Mark Repository as Exempt</a>)</li>")    
                f.write(f"</ul><p>Total Repositories: {len(new_repos_to_archive)}</p><p>These repositories will be archived in <b>{archive_threshold_days} days</b>, unless marked as exempt.</p>")            

            return flask.redirect(f'/manage_repositories?reposAdded={repos_added}')
    
    return flask.redirect('/')
    
@app.route('/manage_repositories')
def manage_repos():
    """
        Returns a render of manageRepositories.html.

        ==========
        
        Loads a list of repositories from repositories.json to display within the render.

        This function can also be passed an arguement called reposAdded, which is used to
        display a success message when being redirected from findRepos().
    """

    # Get repos from storage
    repos = storage_interface.read_file("repositories.json", "name")

    repos_added = flask.request.args.get("reposAdded")

    if repos_added == None:
        repos_added = -1
    else:
        repos_added = int(repos_added)

    status_message = flask.request.args.get("msg")

    if status_message == None:
        status_message = ""

    # When loading repos, check each repo to see if its exempt date has passed
    for i in range(0, len(repos)):
        if repos[i]["exemptUntil"] != "1900-01-01" and datetime.strptime(repos[i]["exemptUntil"], "%Y-%m-%d") < datetime.today():
            repos[i]["dateAdded"] = datetime.strftime(datetime.today(), "%Y-%m-%d")
            repos[i]["exemptUntil"] = "1900-01-01"
            repos[i]["exemptReason"] = ""
    
    storage_interface.write_file("repositories.json", repos)

    return flask.render_template("manageRepositories.html", repos=repos, reposAdded=repos_added, statusMessage=status_message)

@app.route('/clear_repositories')
def clear_repos():
    """ 
        Removes all stored repositories by deleting repositories.json.
        
        Returns a redirect to manage_repositories.
    """
    os.remove("repositories.json")
    return flask.redirect('/manage_repositories')

@app.route('/set_exempt_date', methods=['POST', 'GET'])
def set_exempt_date():
    repo_name = flask.request.args.get("repoName")

    if repo_name == None:
        return flask.redirect("/manage_repositories")

    if flask.request.method == "POST":
        months_select_value = flask.request.form['date']

        if months_select_value == "-1":
            months_select_value = flask.request.form['months']

        exempt_until = datetime.today() + relativedelta(months=int(months_select_value))
        exempt_until = exempt_until.strftime("%Y-%m-%d")
            
        exempt_reason = flask.request.form["reason"]

        # Get repos from storage
        repos = storage_interface.read_file("repositories.json")

        for i in range(0, len(repos)):
            if repos[i]["name"] == repo_name:
                repos[i]["exemptUntil"] = exempt_until
                repos[i]["exemptReason"] = exempt_reason

        storage_interface.write_file("repositories.json", repos)
    
    else:
        return flask.render_template("setExemptDate.html", repoName=repo_name)
    
    try:
        type(flask.session["pat"])
    except KeyError:
        return flask.redirect("/success")
    else:
        return flask.redirect(f"/manage_repositories?msg={repo_name}%20exempt%20date%20has%20been%20set")

@app.route('/clear_exempt_date')
def clear_exempt_date():
    repo_name = flask.request.args.get("repoName")

    if repo_name != None:
        # Get repos from storage
        repos = storage_interface.read_file("repositories.json")

        for i in range(0, len(repos)):
            if repos[i]["name"] == repo_name:
                repos[i]["dateAdded"] = datetime.now().strftime("%Y-%m-%d")
                repos[i]["exemptUntil"] = "1900-01-01"
                repos[i]["exemptReason"] = ""

        storage_interface.write_file("repositories.json", repos)

    return flask.redirect(f"/manage_repositories?msg={ repo_name }%20exempt%20date%20has%20been%20cleared")

@app.route('/download_recently_added')
def download_recently_added():
    return flask.send_file("recentlyAdded.html", as_attachment=True)


# Functions used within archive_repos()
def get_archive_lists(batch_id: int, repos: list) -> tuple[list, list]:
    """
        Archives any repositories older than archive_threshold_days and are not exempt, then logs them in repos_to_remove and archive_instance which get returned.

        ==========

        Args: 
            batch_id (int): the id of the batch within archive_instance.
            repos (list): a list of repositories stored within the system.
        
        Returns:
            repos_to_remove (list)
            archive_instance (list)
    """

    try:
        gh = api_interface.api_controller(flask.session['pat'])
    except KeyError:
        return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')

    archive_instance = {
        "batchID": batch_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "repos": []
    }

    repos_to_remove = []

    # For each repo, if keep is false and it was added to storage over archive_threshold_days days ago,
    # Archive them
    for i in range(0, len(repos)):
        if repos[i]["exemptUntil"] == "1900-01-01":
            if (datetime.now() - datetime.strptime(repos[i]["dateAdded"], "%Y-%m-%d")).days >= archive_threshold_days:
                response = gh.patch(repos[i]["apiUrl"], {"archived":True}, False)

                if response.status_code == 200:

                    archive_instance["repos"].append({
                        "name": repos[i]["name"],
                        "apiurl": repos[i]["apiUrl"],
                        "status": "Success",
                        "message": "Repository Archived Successfully."
                    })

                    repos_to_remove.append(i)

                else:
                    archive_instance["repos"].append({
                        "name": repos[i]["name"],
                        "apiurl": repos[i]["apiUrl"],
                        "status": "Failed",
                        "message": f"Error {response.status_code}: {response.json()["message"]}"
                    })

    return repos_to_remove, archive_instance

@app.route('/archive_repositories', methods=['POST', 'GET'])
def archive_repos():
    """
        Archives any repositories which are:
            - older than archive_threshold_days days within the system
            - have not been marked to be kept using the keep attribute in repositories.json
        
        ==========
        
        Loads any archive batches from archived.json into archiveList.
        Executes get_archive_lists to:
            - Get a list of repos which need removing from storage (repos_to_remove)
            - Archive any repositories older than archive_threshold_days
            - Get a list of repos which have been archived (archive_instance)
        Add the new archiveInstance to archiveList and write it to archived.json.
        Remove any archived repositories from repos and write it to repositories.json.

        Returns a redirect to recentlyArchived.

        If the function fails to create an APIHandler instance, it will return a render of error.html
        with an appropriate error message.

    """

    # Get archive batches from storage
    archive_list = storage_interface.read_file("archived.json")

    # Get repos from storage
    repos = storage_interface.read_file("repositories.json")

    repos_to_remove, archive_instance = get_archive_lists(len(archive_list)+1, repos)

    # If repos have been archived, log changes in storage 
    if len(archive_instance["repos"]) > 0:
        
        archive_list.append(archive_instance)

        storage_interface.write_file("archived.json", archive_list)

        pop_count = 0
        for i in repos_to_remove:
            repos.pop(i - pop_count)
            pop_count += 1

        storage_interface.write_file("repositories.json", repos)
        
        return flask.redirect(f'/recently_archived?msg=Batch%20{archive_instance["batchID"]}%20created')
    
    else:
        return flask.redirect('/manage_repositories?msg=No%20repositories%20eligable%20for%20archive')

@app.route('/recently_archived')
def recently_archived():
    """
        Returns a render of recentlyArchived.html.

        ==========

        Loads a list of archive batches from archived.json to display within the render.

        This function can also be passed an arguement called batchID, which is used to 
        display a success message when redirected from undoBatch().
    """

    # Get archive batches from storage
    archive_list = storage_interface.read_file("archived.json", reverse=True)

    batch_id = flask.request.args.get("batchID")

    if batch_id == None:
        batch_id = ""

    status_message = flask.request.args.get("msg")

    if status_message == None:
        status_message = ""

    return flask.render_template('recentlyArchived.html', archiveList=archive_list, batchID=batch_id, statusMessage=status_message)


# Functions used within undo_batch()
def get_repository_information(gh: api_interface.api_controller, repo_to_undo: dict, batch_id: int) -> dict:
    """
        Gets information for a given repo_to_undo as part of the unarchive process.

        ==========

        Args:
            gh (api_controller): An instance of the api_controller class from api_interface.py.
            repo_to_undo (dict): The repository to get the information of.
            batch_id (int): The id of the batch which the repository belongs to.

        Returns:
            A dictionary of the repo_to_undo's information.
    """

    response = gh.get(repo_to_undo["apiurl"], {}, False)

    if response.status_code != 200:
        return flask.render_template('error.html', pat=flask.session['pat'], error=f"Error {response.status_code}: {response.json()["message"]} <br> Point of Failure: Restoring batch {batch_id}, {repo_to_undo["name"]} to stored repositories")

    repo_json = response.json()

    current_date = datetime.now().strftime("%Y-%m-%d")

    last_update = repo_json["pushed_at"]
    last_update = datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%SZ")
    last_update = date(last_update.year, last_update.month, last_update.day)

    contributor_list = api_interface.get_repo_contributors(gh, repo_json["contributors_url"])

    repository_information = {
        "name": repo_json["name"],
        "type": repo_json["visibility"],
        "contributors": contributor_list,
        "apiUrl": repo_json["url"],
        "lastCommit": str(last_update),
        "dateAdded": current_date,
        "exemptUntil": "1900-01-01",
        "exemptReason": ""
    }

    return repository_information

@app.route('/undo_batch')
def undo_batch():
    """
        Unarchives a batch of archived repositories.

        ==========

        Creates an instance of the APIHandler class from api_controller.py.
        Gets the passed batchID arguement.
        Loads any archive batches from archived.json into archiveList.
        Loads all stored repositories from repositories.json into storedRepos.
        Gets the batch that needs undoing from archiveList using the given batchID.
        Unarchives all repositories within the batch using a patch request from the APIHandler class instance.
        If any now unarchived repositories are not already stored, fetch their information from Github using a get request
        from the APIHandler class instance and add it to storedRepos.
        Remove any now archived repositories from the batch in archiveList.
        
        Write storedRepos back to repositories.json.
        Write archive_list back to archived.json.

        Returns a redirect to recentlyArchived with a passed arguement, batchID, which is used to show a success message.

        If the function fails to create an APIHandler instance, it will return a render of error.html
        with an appropriate error message.

        If the function fails to unarchive a repository or get the repository's information from Github, it will return a render of error.html
        with an appropriate error message.
    """
    try:
        gh = api_interface.api_controller(flask.session['pat'])
    except KeyError:
        return flask.render_template('error.html', pat='', error='Personal Access Token Undefined.')

    batch_id = flask.request.args.get("batchID")

    if batch_id != None:
        batch_id = int(batch_id)

        # Get archive list and stored repos from storage
        archive_list = storage_interface.read_file("archived.json")        
        stored_repos = storage_interface.read_file("repositories.json")

        batch_to_undo = archive_list[batch_id - 1]

        pop_count = 0

        for i in range(0, len(batch_to_undo["repos"])):
            # Unarchive the repo
            response = gh.patch(batch_to_undo["repos"][i - pop_count]["apiurl"], {"archived": False}, False)

            if response.status_code != 200:
                return flask.render_template('error.html', pat=flask.session['pat'], error=f"Error {response.status_code}: {response.json()["message"]} <br> Point of Failure: Unarchiving batch {batch_id}, {batch_to_undo["repos"][i - pop_count]["name"]}")

            if not any(d["name"] == batch_to_undo["repos"][i - pop_count]["name"] for d in stored_repos):
                # Add the repo to repositories.json
                stored_repos.append(get_repository_information(gh, batch_to_undo["repos"][i - pop_count], batch_id))

            # Remove the repo from archived.json
            archive_list[batch_id - 1]["repos"].pop(i - pop_count)
            pop_count += 1

        # Write changes to storage
        storage_interface.write_file("repositories.json", stored_repos)
        storage_interface.write_file("archived.json", archive_list)

        return flask.redirect(f"/recently_archived?batchID={batch_id}")

    return flask.redirect("/")

@app.route('/confirm')
def confirm_action():
    message = flask.request.args.get("message")
    confirm_url = flask.request.args.get("confirmUrl")
    cancel_url = flask.request.args.get("cancelUrl")

    if message != None and confirm_url != None and cancel_url != None:
        return flask.render_template("confirmAction.html", message=message, confirmUrl=confirm_url, cancelUrl=cancel_url)

    return flask.redirect("/")

if __name__ == "__main__":
    app.run(debug=True)