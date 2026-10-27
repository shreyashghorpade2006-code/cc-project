# Cloud-Based To-Do List

A responsive to-do app with a Flask/SQLite local demo and a deployable AWS serverless backend. Tasks can be created, described, edited, completed, filtered, counted, and deleted. The AWS version stores tasks in DynamoDB and plays a completion sound delivered from a private S3 bucket using a short-lived presigned URL.

## Quick start

### Requirements

- Python 3.9 or newer (Python 3.12 is recommended to match the AWS Lambda runtime)
- [Git](https://git-scm.com/downloads)
- A current web browser

### Clone and run on Windows

Open PowerShell in the folder where you want the project, then run:

```powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

If PowerShell prevents virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again. Alternatively, skip activation and run `.venv\Scripts\python.exe -m pip install -r requirements.txt`, followed by `.venv\Scripts\python.exe app.py`.

Open <http://127.0.0.1:5000>. To stop the server, press **Ctrl+C** in PowerShell.

### Clone and run on macOS or Linux

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. To stop the server, press **Ctrl+C** in the terminal.

The local app creates its SQLite database under the ignored `instance/` folder. Each clone gets its own database. No AWS account or credentials are needed for local use.

## Architecture

```text
Browser
  ├── AWS Amplify Hosting serves frontend/
  └── Amazon API Gateway (HTTP API)
        └── AWS Lambda (backend/lambda_function.py)
              ├── Amazon DynamoDB (persistent task records)
              └── Amazon S3 (private MP3; Lambda returns a 15-minute presigned URL)
```

- **Amplify Hosting** serves the static HTML, CSS, and JavaScript over HTTPS.
- **API Gateway** provides HTTPS endpoints and browser CORS support.
- **Lambda** validates requests and performs task operations. Its execution role grants only the DynamoDB task actions and permission to read the one sound object.
- **DynamoDB** stores tasks with on-demand billing, encryption, and point-in-time recovery.
- **S3** stores the MP3. Public access is blocked; the browser can play it only through a time-limited URL signed by Lambda.
- **IAM** gives the Lambda execution role narrowly scoped data permissions. You do not create or embed AWS keys for the website.
- **CloudFormation/SAM** provisions the repeatable backend stack from `template.yaml`.

### Project structure

```text
backend/
  lambda_function.py       # AWS Lambda API handler
  requirements.txt         # Dependencies packaged by SAM
  test_lambda_function.py  # Lambda unit tests
frontend/
  index.html               # Responsive dashboard
  styles.css
  app.js                   # API calls, filters, counts, and audio
  config.js                # Public API URL; no credentials
scripts/
  create_completion_sound.py
app.py                     # Local Flask API and SQLite compatibility
test_app.py                # Local API tests
template.yaml              # AWS SAM infrastructure
amplify.yml                # Amplify static-site build configuration
.github/workflows/tests.yml # Checks tests on GitHub pushes and pull requests
requirements.txt           # Local Flask dependencies
requirements-dev.txt       # Local and Lambda test dependencies
requirements-audio.txt     # Optional MP3 generator dependency
task-completed.mp3         # Generated chime for the private S3 bucket
LICENSE                    # MIT license
```

> **Demo limitation:** AWS API routes are public and use one shared demo task list (partition key `demo`) to keep the college demonstration easy to deploy. Do not store private or sensitive tasks in this version. For a real multi-user app, add Amazon Cognito authentication and authorize each user's DynamoDB partition. The S3 bucket itself remains private; CORS is not a substitute for access control.

The local adapter stores data in `instance/db.sqlite` and supports the same create, edit, complete, filter, count, and delete flows. On its first task request it adds the description column to an older SQLite database if needed. Local mode serves the included MP3 from the app; AWS mode serves it using a presigned URL.

Run local and Lambda tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -v
python -m unittest discover -s backend -v
```

The sound file is a short original chime. Recreate it if needed:

```powershell
python -m pip install -r requirements-audio.txt
python scripts/create_completion_sound.py
```

## Deploy the backend (computer or AWS CloudShell)

The backend stack is defined in `template.yaml`. It creates the HTTP API, Lambda, encrypted on-demand DynamoDB table, and **private** S3 bucket.

### Before deploying

1. Create an AWS account and sign in to the AWS Console. Do not use the root account for routine work. Set an AWS Budget alert under **Billing and Cost Management → Budgets**.
2. Use **AWS CloudShell** from the console (recommended for beginners; it uses your console identity), or install AWS CLI v2 and AWS SAM CLI on your computer. For local terminal deployment, use an AWS IAM Identity Center profile or your organization's approved role—never the root account.
3. If your organization has enabled IAM Identity Center, configure and sign in to a CLI profile:

   ```powershell
   aws configure sso --profile todo-demo
   aws sso login --profile todo-demo
   $env:AWS_PROFILE = "todo-demo"
   aws sts get-caller-identity
   ```

   If you use CloudShell, it already uses your console session, so skip CLI sign-in. Never paste AWS credentials into this project or its frontend. The frontend only needs the public API URL.

### Build and deploy

From the project directory, in a terminal where SAM is installed and AWS credentials are configured:

```powershell
sam --version
sam build --template-file template.yaml
sam deploy --guided
```

For `sam deploy --guided`, choose a stack name such as `todo-demo`, your AWS region, and allow SAM to create the required IAM role. Accept saving the deployment settings. When deployment finishes, copy the `ApiBaseUrl` output. Also note `TaskAudioBucketName`.

If using **CloudShell**, first make a deployment ZIP on your computer:

```powershell
Compress-Archive -Path backend,template.yaml -DestinationPath todo-backend.zip -Force
```

In CloudShell choose **Actions → Upload file**, select `todo-backend.zip`, and run:

```bash
mkdir todo-backend
unzip todo-backend.zip -d todo-backend
cd todo-backend
sam build --template-file template.yaml
sam deploy --guided
```

### Upload the sound in the AWS Console

1. Open **Amazon S3** in the same AWS region and open the bucket named by `TaskAudioBucketName`.
2. Choose **Upload → Add files**, select the project's `task-completed.mp3`, and upload it with the exact key `task-completed.mp3` at the bucket root.
3. In **Permissions**, leave **Block all public access** enabled. Do not add a public bucket policy or make the object public.
4. The SAM stack already grants the Lambda role `s3:GetObject` for that specific key and configures S3 CORS for audio playback. A browser direct request to the ordinary S3 object URL should be denied; the app asks the API for a temporary presigned URL when it needs to play the chime.

### Connect and publish the frontend

1. Install Git if needed. On GitHub, create a **new empty repository**, choose a repository name, and select **Public** so anyone can clone it. Do not initialize the GitHub repository with a README or `.gitignore`; those files are already managed in this project. Choose a license only if you intend to grant reuse rights (see the license note below). Copy the repository's HTTPS URL.
2. From the project folder, initialize Git and push the files (replace the URL with the one GitHub gave you):

   ```bash
   git init
   git branch -M main
   git add .
   git commit -m "Add cloud-based to-do list"
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
   git push -u origin main
   ```

   If Git asks, sign in through your browser or Git Credential Manager. GitHub no longer accepts account passwords for HTTPS Git operations. `.gitignore` excludes virtual environments, local databases, AWS SAM build output, and local AWS settings. Do not commit AWS credentials.
3. Before Amplify's first build, edit `frontend/config.js` and set `apiBaseUrl` to the deployed `ApiBaseUrl` value, for example:

   ```javascript
   window.APP_CONFIG = {
     apiBaseUrl: 'https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com'
   };
   ```

   Keep the URL without a trailing slash. This is a public endpoint, not a credential. Commit and push the config change.
4. In the AWS Console, open **AWS Amplify → Create new app → GitHub**, authorize GitHub, and select the public repository and `main` branch. Amplify reads the project's `amplify.yml`; confirm it publishes `frontend/` and save/deploy.
5. Wait for the branch deployment to show **Deployed**, then open the Amplify-provided public URL.

> For the **local Flask demo**, leave `frontend/config.js` set to `'/api'`. For AWS Amplify, use the API Gateway URL above. Commit the AWS config only for the deployment branch or change it back to `'/api'` when returning to local mode.

## Test the deployed app

1. Open the Amplify URL. Add a task with both a title and description; the task and total/pending counts should update.
2. Refresh the browser. The task should still be there because it is stored in DynamoDB, not browser storage.
3. Edit the task, switch between **All**, **Pending**, and **Completed**, then check the completion box. The completed count updates and the app displays “Task completed successfully!” while attempting to play the S3 chime.
4. Uncheck the task. It returns to Pending and does not play the completion sound. Delete it and confirm the counts update.
5. To verify the S3 object is private, open its ordinary object URL in a private browser window; access should be denied. The app uses a short-lived presigned URL issued by the API instead.
6. Confirm no secrets are present in `frontend/` or `frontend/config.js`. AWS credentials belong only in the AWS CLI/CloudShell identity and the Lambda execution role.

## Services and cost notes

The app uses API Gateway HTTP API, Lambda, DynamoDB on-demand billing, S3, CloudFormation through SAM, and Amplify Hosting. These are pay-as-you-go AWS services; usage, data transfer, region, account age, and current AWS pricing affect cost. Check AWS pricing and configure a budget alert before presenting publicly. Remove the CloudFormation stack when finished if you no longer need its resources; confirm the S3 bucket is empty before stack deletion.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/tasks` | List tasks |
| `POST` | `/tasks` | Create `{ "title": "...", "description": "..." }` |
| `PUT` | `/tasks/{taskId}` | Edit title and description |
| `PATCH` | `/tasks/{taskId}` | Set completion, e.g. `{ "completed": true }` |
| `DELETE` | `/tasks/{taskId}` | Delete a task |
| `GET` | `/audio-url` | Get a 15-minute presigned URL for the private MP3 |

No AWS access keys or secret keys are used by the browser.

## License

This project is released under the [MIT License](./LICENSE). You may use, modify, and redistribute it under the license terms.
