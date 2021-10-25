# import base64
import json
import os
import boto3
import docker
import base64

ECS_CLUSTER = 'py-docker-aws-example-project-cluster'
ECS_SERVICE = 'py-docker-aws-example-project-service'
ECR_REPOSITORY_NAME = "hey-assignment"
LOCAL_REPOSITORY = 'hey-assignment:latest'
EC2_INSTANCE_ID = ''


def main():
    """Build Docker image, push to AWS and update ECS service.

    :rtype: None
    """

    # get AWS credentials
    aws_credentials = read_aws_credentials()
    aws_account_id = aws_credentials['aws_account_id']
    aws_region = aws_credentials['aws_region']
    aws_access_key_id = aws_credentials['aws_access_key_id']
    aws_secret_access_key = aws_credentials['aws_secret_access_key']

    # build Docker image
    print("#### Building Docker Image ####")
    docker_client = docker.from_env()
    image, build_log = docker_client.images.build(
        path='.', tag=LOCAL_REPOSITORY, rm=True)

    # create ECR on AWS
    print("#### Creating ECR '{}' on AWS ####".format(ECR_REPOSITORY_NAME))
    ecr_client = boto3.client(
        'ecr', aws_access_key_id=aws_access_key_id, 
        aws_secret_access_key=aws_secret_access_key, region_name=aws_region)
    try:
        response = ecr_client.create_repository(
            registryId=aws_account_id,
            repositoryName=ECR_REPOSITORY_NAME
        )
    except:
        print('Repository name "{}" already exists in registry with id {}'
              .format(ECR_REPOSITORY_NAME, aws_account_id))

    # get AWS ECR login token
    print("#### Getting AWS ECR login token ####")
    ecr_client = boto3.client(
        'ecr', aws_access_key_id=aws_access_key_id, 
        aws_secret_access_key=aws_secret_access_key, region_name=aws_region) 
    ecr_credentials = (
        ecr_client
        .get_authorization_token()
        ['authorizationData'][0])
    ecr_username = 'AWS'
    ecr_password = (
        base64.b64decode(ecr_credentials['authorizationToken'])
        .replace(b'AWS:', b'')
        .decode('utf-8'))
    ecr_url = ecr_credentials['proxyEndpoint']

    # get Docker to login/authenticate with ECR
    print("#### Docker client authenticating with ECR ####")
    docker_client.login(
        username=ecr_username, password=ecr_password, registry=ecr_url)

    # tag image for AWS ECR
    ecr_repo_name = '{}/{}'.format(
        ecr_url.replace('https://', ''), ECR_REPOSITORY_NAME)
    image.tag(ecr_repo_name, tag='latest')

    # push image to AWS ECR
    print("#### Pushing Docker Image to ECR '{}' ####".format(ECR_REPOSITORY_NAME))
    push_log = docker_client.images.push(ecr_repo_name, tag='latest')

    ecs_client = boto3.client(
        'ecs', aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key, region_name=aws_region)
    response = ecs_client.list_clusters(
        maxResults=50
    )
    if 'arn:aws:ecs:{}:{}:cluster/{}'.format(aws_region, aws_account_id, ECR_REPOSITORY_NAME) not in response['clusterArns']:
        # create ECS on AWS
        print("#### Creating ECS cluster '{}' on AWS ####"
              .format(ECR_REPOSITORY_NAME))
        try:
            response = ecs_client.create_cluster(
                clusterName=ECR_REPOSITORY_NAME,
            )
        except:
            print('Cluster name "{}" already exists'
                  .format(ECR_REPOSITORY_NAME))
    
        # create EC2 on AWS
        print("#### Creating EC2 instance '{}' on AWS ####"
              .format(ECR_REPOSITORY_NAME))
        ec2_client = boto3.client(
            'ec2', aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key, region_name=aws_region)
        try:
            response = ec2_client.run_instances(
                # Use the official ECS image
                ImageId="ami-0a4cbf3bd47ef1bc9",
                MinCount=1,
                MaxCount=1,
                InstanceType="t2.micro",
                IamInstanceProfile={
                    "Name": "ecsInstanceRole"
                },
                UserData="#!/bin/bash \n echo ECS_CLUSTER=" + ECR_REPOSITORY_NAME + " >> /etc/ecs/ecs.config"
            )
            EC2_INSTANCE_ID = response['Instances'][0]['InstanceId']
        except:
            print('EC2 name "{}" already exists'
                  .format(ECR_REPOSITORY_NAME))
        
        # Create a task definition
        print("#### Creating ECS task definition '{}' on AWS ####"
              .format(ECR_REPOSITORY_NAME))
        try:
            response = ecs_client.register_task_definition(
                containerDefinitions=[
                    {
                        "name": ECR_REPOSITORY_NAME + '-container',
                        "image": ecr_repo_name + ':latest',
                        "essential": True,
                        "portMappings": [
                            {
                                "containerPort": 80,
                                "hostPort": 80
                            }
                        ],
                        "memory": 300,
                        "cpu": 10
                    }
                ],
                family=ECR_REPOSITORY_NAME
        )
        except:
            print('Task definition name "{}" already exists in the ECS Cluster'
                  .format(ECR_REPOSITORY_NAME))
        
        # Create the service to run the image
        print("#### Creating ECS service '{}' on AWS ####"
              .format(ECR_REPOSITORY_NAME))
        response = ecs_client.create_service(
            cluster=ECR_REPOSITORY_NAME,
            serviceName=ECR_REPOSITORY_NAME + '-service',
            taskDefinition=ECR_REPOSITORY_NAME,
            desiredCount=5,
            deploymentConfiguration={
                'minimumHealthyPercent': 0,
                'maximumPercent': 100
        }
    )
        response = ec2_client.describe_instances(
            InstanceIds=[
                EC2_INSTANCE_ID,
            ]
        )
        ec2_url = response['Reservations'][0]['Instances'][0]['PublicDnsName']
        with open("aws_credentials.json", 'r+') as file:
            file_data = json.load(file)
            file_data['aws_ec2_url'] = ec2_url
            file.seek(0)
            json.dump(file_data, file, indent=4)
        print("#### The changes can be seen on http://{} ####".format(ec2_url))
    else:
        print("#### Updating ECS service '{}' on AWS ####".format(ECR_REPOSITORY_NAME))
        response = ecs_client.update_service(
            cluster=ECR_REPOSITORY_NAME, service="hey-assignment-service", forceNewDeployment=True)
        with open('aws_credentials.json') as json_data:
            credentials = json.load(json_data)
            print("#### The changes can be seen on http://{} ####".format(credentials['aws_ec2_url']))

    return None


def read_aws_credentials(filename='aws_credentials.json'):
    try:
        with open(filename) as json_data:
            credentials = json.load(json_data)

        for variable in ('aws_account_id', 'aws_region', 'aws_access_key_id',
                         'aws_secret_access_key'):
            if variable not in credentials.keys():
                msg = '"{}" cannot be found in {}'.format(variable, filename)
                raise KeyError(msg)                                
    except FileNotFoundError:
        print("File does not exist")
    return credentials


if __name__ == '__main__':
    main()
