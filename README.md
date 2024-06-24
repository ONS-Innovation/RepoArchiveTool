# Github API App

A Python application to archive outdated organisation repositories.

## Prerequisites

This project uses poetry for package management, colima a license free tool for containerisation and the AWS cli commands for deploying changes.

It is expected you have these tools installed before progressing further.

[Instructions to install Poetry](https://python-poetry.org/docs/)

[Instructions to install Colima](https://github.com/abiosoft/colima/blob/main/README.md)

[Instructions to install AWS cli tool](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

## Setup - Run outside of Docker

1. Navigate into the project's folder and create a virtual environment

    ```bash
    python3 -m venv <environment_name>
    ```

2. Activate the environment

    ```bash
    source <environment_name>/bin/activate
    ```

3. Install the required dependencies

    ```bash
    poetry install
    ```

4. Get the repo-archive-github.pem file and copy to the source code root directory (see "Getting a .pem file" below).

5. When running the project locally, you need to edit `get_s3_client()` within `storage_interface.py`.

When creating an instance of `boto3.session()`, you must pass which AWS credential profile to use, as found in `~/.aws/credentials`.

When running locally:

```
session = boto3.Session(profile_name="<profile_name>")
s3 = session.client("s3")
```

When running from a container:

```
session = boto3.Session()
s3 = session.client("s3")
```

6. Run the project

```bash
poetry run python3 repoarchivetool/app.py
```

## Building a docker image

Build and tag the image

```bash
docker build -t repo-archive-tool .
```

Check the image is available locally

```bash
docker images
```

Example output:

```bash
REPOSITORY                                                      TAG       IMAGE ID       CREATED          SIZE
repo-archive-tool                                               latest    d9c802cef7eb   11 seconds ago   332MB
```

Run the image locally mapping local host port (5000) to container port (5000) and passing in AWS credentials to download a .pem file from the AWS Secrets Manager to the running container.

The credentials used in the below command are for a user in AWS that has permissions to retrieve secrets from AWS Secrets Manager.

```bash
code-repo-archive-tool % docker run -p 5000:5000 \                
-e AWS_ACCESS_KEY_ID=<aws_access_key_id> \
-e AWS_SECRET_ACCESS_KEY=<aws_secret_access_key_id> \
-e AWS_DEFAULT_REGION=eu-west-2 \
repo-archive-tool
```

To check the container is running

```bash
docker ps 
```

Example output

```bash
CONTAINER ID   IMAGE               COMMAND                  CREATED          STATUS          PORTS                                       NAMES
e85a3ce5fecf   repo-archive-tool   "/app/start_repo_too…"   27 seconds ago   Up 25 seconds   0.0.0.0:5000->5000/tcp, :::5000->5000/tcp   cranky_yalow
```

To view the running application in a browser navigate to

```bash
Running on http://127.0.0.1:5000
```

To stop the running container either use the container ID:

```bash
docker stop e85a3ce5fecf
```

or the container name

```bash
docker stop cranky_yalow
```

## Storing the container on AWS Elastic Container Registry (ECR)

When you make changes to the application a new container image must be pushed to ECR.

These instructions assume:

1. You have a repository set up in your AWS account named sdp-repo-archive.
2. You have created an AWS IAM user with permissions to read/write to ECR (e.g AmazonEC2ContainerRegistryFullAccess policy) and that you have created the necessary access keys for this user.  The credentials for this user are stored in ~/.aws/credentials and can be used by accessing --profile <aws-credentials-profile\>, if these are the only credentials in your file then the profile name is _default_

You can find the AWS repo push commands under your repository in ECR by selecting the "View Push Commands" button.  This will display a guide to the following (replace <aws-credentials-profile\>, <aws-account-id\> and <version\> accordingly):

1. Get an authentication token and authenticate your docker client for pushing images to ECR:

    ```bash
    aws ecr --profile <aws-credentials-profile> get-login-password --region eu-west-2 | docker login --username AWS --password-stdin <aws-account-id>.dkr.ecr.eu-west-2.amazonaws.com
    ```

2. Tag your latest built docker image for ECR (assumes you have run _docker build -t sdp-repo-archive ._ locally first)

    ```bash
    docker tag sdp-repo-archive:latest <aws-account-id>.dkr.ecr.eu-west-2.amazonaws.com/sdp-repo-archive:<version>
    ```

    **Note:** To find the <version\> to build look at the latest tagged version in ECR and increment appropriately

3. Push the version up to ECR

    ```bash
    docker push <aws-account-id>.dkr.ecr.eu-west-2.amazonaws.com/sdp-repo-archive:<version>
    ```

## Updating the running application to use the new image

Update via IaC or CLI is **TBD**.

To run the newly pushed container image you must currently use the AWS
Management Console.

1. Login to the relevant AWS Account in a browser
2. Navigate to Elastic Container Service and find the Service Cluster (service-cluster) and find the related Task Definition (under the Tasks tab), this will show the latest revision of the task definition (e.g ecs-service-sdp-application:4)
3. Navigate to the Task Definition, select the appropriate task definition name and create a new **_revision_** (note: **_not_** a new task definition)
4. Find the Container Section and update the <version\> of the image to your new image version. No other values need to change.
5. After saving the task definition, select the Task Definition name and choose Deploy->Update Service
6. In the Update Service configuration select Force New Deployment and ensure the following are set:

    - Revision : matches the task definition revision you just created
    - Desired Tasks : 1
    - Min Running Tasks: 100%
    - Max Running Tasks: 200%

    Click on Update to trigger the deployment.

The deployment will take a couple of minutes, you should see two tasks running temporarily (the new one and the existing running task). Once the new task is deployed the original task container will drain and stop.

Your service should now be running the new image.

## Getting a .pem file for the Github App

A .pem file is used to allow the project to make authorised Github API requests through the means of Github App authentication.
The project uses authentication as a Github App installation ([documentation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)).

In order to get a .pem file, a Github App must be created an installed into the organisation of which the app will be managing.
This app should have **Read and Write Administration** permission and **read-only Metadata** permission.

Once created and installed, you need to generate a Private Key for that Github App. This will download a .pem file to your pc.
This file needs to be renamed **repo-archive-tool.pem** ([documentation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps)).

If you do not have access to organisation settings, you need to request a .pem file for the app.