gcloud config set project a-darker-vision

gcloud functions deploy serve_cv_from_git --gen2 --runtime python311 --region europe-west1 --source . --entry-point serve_cv_from_git --trigger-http --allow-unauthenticated --set-env-vars "GCP_PROJECT=a-darker-vision,GIT_REPO_URL_SECRET_ID=cv-git-repo-url,CV_MD_FILE_SECRET_ID=cv-md-file-path"