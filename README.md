# docker-aws-py

Following are the files and their uses.

1) Pipfile - contains the dependencies to be installed
2) aws_credentials.json - contains the access keys to interact with the AWS resources.
3) deploy_aws.py - the python file to run for creating the resources on AWS.
4) index.html - the html file that's getting deployed to ECS cluster.
5) Dockerfile - the file containing the steps to dockerize the application.

Steps to Run.
1) install the Pipenv package using pip if not exising

pip install pipenv

2) install the dependencies.

pipenv install --dev

3) Activate the virtual environment.

pipenv shell

4) Update your credentials in aws_credentials.json file

5) Run the deploy_aws.py file

python deploy_aws.py

6) If you like to update the code, edit "index.html" file.