import functions_framework
from git import Repo, exc
import markdown
import os
import shutil # For removing directories
from google.cloud import secretmanager # Added for Secret Manager

# --- Configuration ---
# Environment variables your function will use:
#
# Option 1: Using Secret Manager (Recommended)
#   GCP_PROJECT: (Automatically available) Your Google Cloud Project ID.
#   GIT_REPO_URL_SECRET_ID: The ID of the secret in Secret Manager holding the Git repo URL.
#   CV_MD_FILE_SECRET_ID: The ID of the secret in Secret Manager holding the path to cv.md in the repo.
#
# Option 2: Direct Environment Variables (Fallback)
#   GIT_REPO_URL: The HTTPS URL of your Git repository.
#   CV_MD_FILE_IN_REPO: The path to your cv.md file within the repository.

LOCAL_REPO_PATH = "/tmp/cv_repo" # Cloud Functions can only write to /tmp

def _get_secret_value(project_id: str, secret_id: str, version_id: str = "latest") -> str | None:
    """
    Retrieves a secret value from Google Cloud Secret Manager.
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret '{secret_id}' in project '{project_id}': {e}")
        return None

def fetch_and_read_cv(repo_url, cv_file_path_in_repo):
    """
    Clones or pulls the latest version of the repo and reads the cv.md file.
    Returns the markdown content as a string.
    """
    # Ensure the target directory for cloning is clean or non-existent
    if os.path.exists(LOCAL_REPO_PATH):
        try:
            repo = Repo(LOCAL_REPO_PATH)
            # Check if the remote URL matches, otherwise, re-clone
            if repo.remotes.origin.url != repo_url:
                print(f"Remote URL mismatch. Expected {repo_url}, got {repo.remotes.origin.url}. Re-cloning.")
                shutil.rmtree(LOCAL_REPO_PATH)
                Repo.clone_from(repo_url, LOCAL_REPO_PATH, depth=1) # Shallow clone for speed
            else:
                print(f"Fetching latest changes from {repo_url} into {LOCAL_REPO_PATH}")
                origin = repo.remotes.origin
                origin.pull()
        except exc.GitCommandError as e:
            print(f"Error pulling repo: {e}. Attempting to re-clone.")
            shutil.rmtree(LOCAL_REPO_PATH) # Clean up potentially corrupted repo
            Repo.clone_from(repo_url, LOCAL_REPO_PATH, depth=1)
        except Exception as e: # Catch other potential issues with existing repo
            print(f"Unexpected error with existing repo: {e}. Attempting to re-clone.")
            shutil.rmtree(LOCAL_REPO_PATH)
            Repo.clone_from(repo_url, LOCAL_REPO_PATH, depth=1)
    else:
        print(f"Cloning {repo_url} into {LOCAL_REPO_PATH}")
        Repo.clone_from(repo_url, LOCAL_REPO_PATH, depth=1) # Shallow clone for speed

    md_file_full_path = os.path.join(LOCAL_REPO_PATH, cv_file_path_in_repo)

    if not os.path.exists(md_file_full_path):
        raise FileNotFoundError(f"Markdown file '{cv_file_path_in_repo}' not found in the repository at '{md_file_full_path}'.")

    with open(md_file_full_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    return md_content

def get_basic_styling():
    """Returns some basic CSS for styling the HTML page."""
    return """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; background-color: #f8f9fa; color: #212529; }
        .container { max-width: 800px; margin: 30px auto; padding: 25px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1, h2, h3, h4, h5, h6 { color: #343a40; margin-top: 1.5em; margin-bottom: 0.5em; }
        h1 { border-bottom: 2px solid #dee2e6; padding-bottom: 0.3em; }
        h2 { border-bottom: 1px solid #e9ecef; padding-bottom: 0.3em; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        ul, ol { padding-left: 20px; margin-bottom: 1em;}
        li { margin-bottom: 0.3em; }
        p { margin-bottom: 1em; }
        code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace; background-color: #e9ecef; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%;}
        pre { background-color: #e9ecef; padding: 15px; border-radius: 5px; overflow-x: auto; }
        pre code { background-color: transparent; padding: 0; font-size: 100%;}
        strong { font-weight: 600; }
    </style>
    """

@functions_framework.http
def serve_cv_from_git(request):
    """HTTP Cloud Function.
    Fetches a Markdown file from a Git repo, converts to HTML, and serves it.
    Args:
        request (flask.Request): The request object.
    Returns:
        HTML content as a string with 'text/html' Content-Type, or an error message.
    """
    try:
        gcp_project = os.environ.get("GCP_PROJECT") # Automatically available in GCF
        git_repo_url_secret_id = os.environ.get("GIT_REPO_URL_SECRET_ID")
        cv_md_file_secret_id = os.environ.get("CV_MD_FILE_SECRET_ID")

        # --- Diagnostic prints ---
        print(f"DEBUG: GCP_PROJECT = '{gcp_project}' (type: {type(gcp_project)})")
        print(f"DEBUG: GIT_REPO_URL_SECRET_ID = '{git_repo_url_secret_id}' (type: {type(git_repo_url_secret_id)})")
        print(f"DEBUG: CV_MD_FILE_SECRET_ID = '{cv_md_file_secret_id}' (type: {type(cv_md_file_secret_id)})")
        # --- End Diagnostic prints ---

        git_repo_url = None
        cv_md_file_in_repo = None

        # Attempt to fetch from Secret Manager first
        if gcp_project and git_repo_url_secret_id:
            print(f"Attempting to fetch GIT_REPO_URL from Secret Manager (secret ID: {git_repo_url_secret_id})")
            git_repo_url = _get_secret_value(gcp_project, git_repo_url_secret_id)
        
        if gcp_project and cv_md_file_secret_id:
            print(f"Attempting to fetch CV_MD_FILE_IN_REPO from Secret Manager (secret ID: {cv_md_file_secret_id})")
            cv_md_file_in_repo = _get_secret_value(gcp_project, cv_md_file_secret_id)

        # Fallback to direct environment variables if secrets weren't fetched
        if not git_repo_url:
            git_repo_url = os.environ.get("GIT_REPO_URL")
            if git_repo_url:
                 print("Using GIT_REPO_URL from direct environment variable.")
        if not cv_md_file_in_repo:
            cv_md_file_in_repo = os.environ.get("CV_MD_FILE_IN_REPO")
            if cv_md_file_in_repo:
                print("Using CV_MD_FILE_IN_REPO from direct environment variable.")
            else: # Default if not set by secret or direct env var
                cv_md_file_in_repo = "cv.md"
                print(f"CV_MD_FILE_IN_REPO not configured, defaulting to '{cv_md_file_in_repo}'.")


        if not git_repo_url:
            error_msg = "Error: GIT_REPO_URL is not configured. " \
                        "Set GIT_REPO_URL_SECRET_ID (and ensure GCP_PROJECT is available) " \
                        "or GIT_REPO_URL environment variables for the Cloud Function."
            print(error_msg)
            return error_msg, 500
        
        # The original code had a placeholder check, which is good to keep if direct env var is used.
        # For secrets, the _get_secret_value would return None on failure.
        if git_repo_url == "YOUR_GIT_REPO_URL_HERE": # Check if placeholder is still there from direct env var
             return "Error: GIT_REPO_URL environment variable is set to a placeholder value. Please configure it correctly.", 500


        print(f"Attempting to serve: {cv_md_file_in_repo} from {git_repo_url}")

        md_content = fetch_and_read_cv(git_repo_url, cv_md_file_in_repo)
        
        html_body = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])

        full_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Curriculum Vitae</title>
            {get_basic_styling()}
        </head>
        <body>
            <div class="container">
                {html_body}
            </div>
        </body>
        </html>
        """
        return full_html, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return str(e), 404
    except exc.GitCommandError as e:
        print(f"Git command error: {e}")
        return f"Git command error: {e.stderr}", 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "An unexpected error occurred while processing your request.", 500
