# heavily borrowed from https://github.com/tomcz/aws_py/blob/master/ec2/aws.py
import sys
import os
import time

from boto.ec2 import connect_to_region
from ConfigParser import SafeConfigParser

# DEFINE YOUR AWS AND EC2 INSTANCE DETAILS
USERNAME = '' # ubuntu
AMI_ID = '' # ami-e4d42d8d
INSTANCE_TYPE = '' # m1.small
INSTANCES_FILE = '' # os.path.join(os.getenv('HOME'), '.aws', 'aws_instances')
EC2_REGION = '' #us-east-1
EC2_SSH_KEY_NAME = '' # inspired
EC2_SSH_KEY_PATH = '' # /Users/johnnydobbins/Documents/code/aws/inspired.pem
ACCESS_KEY = '' # get from aws
SECRET_KEY = '' # get from aws

# import creds from non version controlled file
try:
    from creds import *
except ImportError:
    pass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class Node:
    def __init__(self, public_dns_name):
        self.hostname = public_dns_name
        self.ssh_key_file = EC2_SSH_KEY_PATH
        self.ssh_user = USERNAME

def provision_with_boto(name):
    config = read_config()
    if config.has_section(name):
        return Node(config.get(name, 'public_dns_name'))
    else:
        return Node(run_instance(name))

def connect():
    access_key = ACCESS_KEY
    secret_key = SECRET_KEY
    return connect_to_region(EC2_REGION, aws_access_key_id=access_key, aws_secret_access_key=secret_key)

def run_instance(name):
    conn = connect()
    res = conn.run_instances(AMI_ID, key_name=EC2_SSH_KEY_NAME, instance_type=INSTANCE_TYPE)
    instance = res.instances[0]

    print "Waiting for", name, "to start ...(20 seconds wait)"
    time.sleep(20)
    instance.update()

    while instance.state != 'running':
        time.sleep(10)
        instance.update()

    conn.create_tags([instance.id], {'Name': name})

    config = read_config()
    config.add_section(name)
    config.set(name, 'instance_id', instance.id)
    config.set(name, 'public_dns_name', instance.public_dns_name)
    write_config(config)

    return instance.public_dns_name

def terminate_instance(name):
    print 'Shutting down', name, '...'

    config = read_config()
    instance_id = config.get(name, 'instance_id')

    conn = connect()
    conn.terminate_instances([instance_id])

    config.remove_section(name)
    write_config(config)

def terminate_all_instances():
    conn = connect()
    for reservation in conn.get_all_instances():
        for instance in reservation.instances:
            instance.terminate()
    if os.path.isfile(INSTANCES_FILE):
        os.remove(INSTANCES_FILE)

def write_config(config):
    with open(INSTANCES_FILE, 'w') as fp:
        config.write(fp)

def read_config():
    config = SafeConfigParser()
    if os.path.isfile(INSTANCES_FILE):
        with open(INSTANCES_FILE) as fp:
            config.readfp(fp)
    return config

def public_dns(name):
    config = read_config()
    return config.get(name, 'public_dns_name')