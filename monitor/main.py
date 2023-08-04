#!/usr/bin/python

import openshift as oc
import time
import os
import sys
import re
import logging

from prometheus_client import start_http_server, Enum, Counter

import boto3
import botocore

MONITOR_NAME = "sre-stuck-ebs-volume"
PROJECT = "openshift-monitoring"
VALID_STATES = [ "attaching", "attached", "detaching", "detached" ]

#clusterid is included to better support future Prometheus federation.
VOLUME_STATE = Enum('ebs_volume_state','EBS Volume state',["vol_name","clusterid","namespace","instance_id"],
                states = VALID_STATES)

# A list (implemented as a Set) of all non-deleted volumes.
# After we get a list of all volume IDs from our running instances we will run
# a query against the API for the volumes we know about and prune as needed.
ACTIVE_VOLUMES = set([])

BOTO_ERRS = Counter('boto_exceptions', 'The total number of boto exceptions')

def normalize_prometheus_label(str):
    """
    Prometheus labels must match /[a-zA-Z_][a-zA-Z0-9_]*/ and so we should coerce our data to it.
    Source: https://prometheus.io/docs/concepts/data_model/
    Every invalid character will be made to be an underscore `_`.
    """
    return re.sub(r'[^[a-zA-Z_][a-zA-Z0-9_]*]',"_",str,0)

def check_ebs_volumes_for_cluster(aws,clusterid):
    """
    Get all volumes from AWS, but only those in use by our cluster, then dump the metrics.
    Note: It is important to filter by cluster id to prevent two clusters sharing
    an account each paging for the same volume.
    """

    # get the instances that are in use by our cluster.
    instances = aws.describe_instances(Filters=[
        {
            'Name':   'tag:kubernetes.io/cluster/' + clusterid,
            'Values': ['owned']
        }
    ])
    normalized_clusterid = normalize_prometheus_label(clusterid)

    # the volumes we've seen on this iteration. later, if we haven't seen a volume,
    # we will purge it from VOLUME_STATES
    seen_volumes = set([])

    # iterate through all the volumes
    for reservation in instances["Reservations"]:
        for instance in reservation["Instances"]:
            for block_device_map in instance["BlockDeviceMappings"]:
                if block_device_map["Ebs"]["Status"] not in VALID_STATES:
                    logging.warning("clusterid='%s', vol_name='%s' in unknown state. Got state='%s'",clusterid,block_device_map["Ebs"]["VolumeId"],block_device_map["Ebs"]["Status"])
                else:
                    # Get tags on the EBS volume for namespace
                    namespace = ""
                    volume_response = aws.describe_volumes(VolumeIds=[block_device_map["Ebs"]["VolumeId"]])
                    tags = volume_response["Volumes"][0]["Tags"]
                    for tag in tags:
                        if tag['Key'] == "kubernetes.io/created-for/pvc/namespace":
                            namespace = tag['Value']
                    
                    normalized_vol_id = normalize_prometheus_label(block_device_map["Ebs"]["VolumeId"])
                    # Add the volume to the set
                    ACTIVE_VOLUMES.add(block_device_map["Ebs"]["VolumeId"])
                    seen_volumes.add(block_device_map["Ebs"]["VolumeId"])
                    VOLUME_STATE.labels(normalized_vol_id,normalized_clusterid,namespace,instance["InstanceID"]).state(block_device_map["Ebs"]["Status"])

    for inactive_volume in ACTIVE_VOLUMES - seen_volumes:
        logging.info("Removing vol_name='%s' for clusterid='%s' from Prometheus ",inactive_volume,clusterid)
        VOLUME_STATE.remove(normalize_prometheus_label(inactive_volume),normalized_clusterid)
        ACTIVE_VOLUMES.remove(inactive_volume)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
    clusterid = ""
    if "AWS_CONFIG_FILE" not in os.environ:
        logging.error("Expected to have AWS_CONFIG_FILE set in the environment. Exiting...")
        exit(1)
    if "AWS_SHARED_CREDENTIALS_FILE" not in os.environ:
        logging.error("Expected to have AWS_SHARED_CREDENTIALS_FILE set in the environment. Exiting...")
        exit(1)
    if "CLUSTERID" not in os.environ:
        logging.error("Expected to have CLUSTERID in environment. Exiting")
        exit(1)
    clusterid = os.environ.get("CLUSTERID")

    aws = boto3.client('ec2')

    logging.info('Starting up metrics endpoint')
    # Start up the server to expose the metrics.
    start_http_server(8080)
    while True:
        try:
            check_ebs_volumes_for_cluster(aws,clusterid)
        except botocore.exceptions.ClientError as err:
            BOTO_ERRS.inc()
            logging.error("Caught boto error")
            logging.error('Error Message: {}'.format(err.response['Error']['Message']))
            logging.error('Request ID: {}'.format(err.response['ResponseMetadata']['RequestId']))
            logging.error('Http code: {}'.format(err.response['ResponseMetadata']['HTTPStatusCode']))
        finally:
            time.sleep(60)
