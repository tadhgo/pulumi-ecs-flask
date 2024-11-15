import pulumi
import pulumi_aws as aws
import json

config = pulumi.Config()

## vpc
vpc = aws.ec2.Vpc("app-vpc",
    cidr_block="172.16.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True
)

igw = aws.ec2.InternetGateway("igw",
    vpc_id=vpc.id
)

## public subnet resources
public_route_table = aws.ec2.RouteTable("public-route-table",
    vpc_id=vpc.id,
    routes=[
        {
            "cidr_block": "0.0.0.0/0",
            "gateway_id": igw.id
        }
    ]
)

public_subnet = aws.ec2.Subnet("public-subnet",
    vpc_id=vpc.id,
    cidr_block="172.16.1.0/24",
    opts=pulumi.ResourceOptions(depends_on=[vpc])
)

public_rt_association = aws.ec2.RouteTableAssociation("public-rt-association",
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id
)

## private subnet resources
private_route_table = aws.ec2.RouteTable("private-route-table",
    vpc_id=vpc.id,
    routes=[
        {
            "cidr_block": vpc.cidr_block,
            "gateway_id": "local"
        }
    ]
)

private_subnet = aws.ec2.Subnet("private-subnet",
    vpc_id=vpc.id,
    cidr_block="172.16.2.0/24",
    opts=pulumi.ResourceOptions(depends_on=[vpc])
)

private_rt_association = aws.ec2.RouteTableAssociation("private-rt-association",
    subnet_id=private_subnet.id,
    route_table_id=private_route_table.id
)

## sg to allow access
task_security_group = aws.ec2.SecurityGroup("task-sg",
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol="tcp",
        from_port=80,
        to_port=80,
        cidr_blocks=["0.0.0.0/0"]
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"]
    )]
)




## ecs IAM role
task_execution_role = aws.iam.Role("task-execution-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }]
    })
)

task_execution_role_policy = aws.iam.RolePolicyAttachment("task-execution-role-policy",
    role=task_execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
)



## ecs resources
cluster = aws.ecs.Cluster("pulumi-cluster",
    name="pulumi-cluster",
)

task_definition = aws.ecs.TaskDefinition("flask-task",
    family="flask-task",
    cpu="256",
    memory="512",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    runtime_platform=aws.ecs.TaskDefinitionRuntimePlatformArgs(
        cpu_architecture="ARM64",
        operating_system_family="LINUX"
    ),
    container_definitions=json.dumps([{
        "name": "flask-webserver",
        "image": f"{aws.ecr.get_repository(name='pulumi-repo').repository_url}:latest", ## uploaded image beforehand - wasn't sure if awsx was allowed for ECR 
        "essential": True,
        "portMappings": [{
            "containerPort": 80,
            "protocol": "tcp"
        }],
        "environment": [{
            "name": "CUSTOM_MESSAGE",
            "value": config.require("custom_message")
        }]
    }]),
    execution_role_arn=task_execution_role.arn
)

ecs_service = aws.ecs.Service("flask-service",
    cluster=cluster.id,
    task_definition=task_definition.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=[public_subnet.id],
        security_groups=[task_security_group.id], 
        assign_public_ip=True
    ),
    opts=pulumi.ResourceOptions(depends_on=[cluster])
)