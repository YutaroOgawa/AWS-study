from aws_cdk import (
    Duration,
    Stack,
    SecretValue,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct

class CdkappStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create a vpc with IpAddresses 10.10.0.0/16, a NAT gateway, a public subnet, PRIVATE_WITH_EGRESS subnet and a RDS subnet
        vpc = ec2.Vpc(
            self,
            "MyVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.10.0.0/16"),
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="PrivateWithEgress",
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    name="RDS",
                    cidr_mask=24,
                ),
            ],
        )
        
        # create a security group for the load balancer
        lb_sg = ec2.SecurityGroup(self,"lb_sg",
            vpc=vpc,
            allow_all_outbound=True
        )
        
        # create a security group for the EC2 instance
        rds_sg = ec2.SecurityGroup(self,"rds_sg",
            vpc=vpc,
            allow_all_outbound=True
        )
        
        # create a security group for the EC2 instance
        ec2_sg = ec2.SecurityGroup(self,"ec2_sg",
            vpc=vpc,
            allow_all_outbound=True
        )
        
        
        # add ingress rules for the load balancer to allow all traffic
        lb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80)
        )
        
        # add ingress rule for the EC2 instance to allow 8443 traffic from the load balancer
        ec2_sg.add_ingress_rule(
            peer=lb_sg,
            connection=ec2.Port.tcp(8443)
        )
        
        
        # add ingress rule for the RDS instance to allow 3306 from the EC2 instance
        rds_sg.add_ingress_rule(
            peer=ec2_sg,
            connection=ec2.Port.tcp(3306)
        )
        
        # add ingress rule for the RDS instance to allow 22 from the EC2 instance
        rds_sg.add_ingress_rule(
            peer=ec2_sg,
            connection=ec2.Port.tcp(22)
        )
        
        
        # create an rds aurora mysql cluster
        cluster = rds.DatabaseCluster(
            self,
            "MyDatabase",
            engine=rds.DatabaseClusterEngine.aurora_mysql(version = rds.AuroraMysqlEngineVersion.VER_3_04_0),
            # credentials using testuser and password1234!
            credentials=rds.Credentials.from_password(
                username="testuser",
                password=SecretValue("password1234!")
            ),
            # add default database name Population
            default_database_name="Population",
            instance_props=rds.InstanceProps(
                # add a security group to the rds instance
                vpc=vpc,
                # add a security group to the rds instance
                security_groups=[rds_sg],
                # add a private subnet to the rds instance
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
            ), 
            instances=1,
            )
        
        # create an Amazon Linux 2 image
        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE,
        )

        # read userdata file from cdkapp directory
        with open("cdkapp/userdata.sh", "r") as f:
            user_data = f.read()
            
        # create a t2.small ec2 instance for the web server in a private egress subnet and vpc.availability_zones[0]
        ec2_instance = ec2.Instance(
            self,
            "MyInstance",
            instance_type=ec2.InstanceType("t2.small"),
            machine_image=amzn_linux,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            availability_zone=vpc.availability_zones[0],
            security_group=ec2_sg,
            user_data=ec2.UserData.custom(user_data),
            # add an existing role with name ec2_instance_role
            role=iam.Role.from_role_name(
                self,
                "ec2_instance_role",
                role_name="ec2_instance_role"
            ),
        )
        
        # 【DIY】
        # create a t2.small ec2 instance for the web server in a private egress subnet and vpc.availability_zones[1]
        ec2_instance2 = ec2.Instance(
            self,
            "MyInstance2",
            instance_type=ec2.InstanceType("t2.small"),
            machine_image=amzn_linux,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            availability_zone=vpc.availability_zones[1],
            security_group=ec2_sg,
            user_data=ec2.UserData.custom(user_data),
            # add an existing role with name ec2_instance_role
            role=iam.Role.from_role_name(
                self,
                "ec2_instance_role2",
                role_name="ec2_instance_role"
            ),
        )
        
        
        # create a load balancer for the web server
        lb = elbv2.ApplicationLoadBalancer(
            self,
            "MyLoadBalancer",
            vpc=vpc,
            internet_facing=True,
            security_group=lb_sg
        )
        
        
        # add targets to the load balancer
        listener = lb.add_listener("Listener",
            port=80,
            open=True,
        )
        
        # add targets to the load balancer
        listener.add_targets(
            "Targets",
            port=80,
        )
        
        # add depends on for the web server to wait for the RDS cluster
        ec2_instance.node.add_dependency(cluster)
        
        
        # add depends on for the listener to wait for the web server
        listener.node.add_dependency(ec2_instance)
        
        # 【DIY】
        listener.node.add_dependency(ec2_instance2)


