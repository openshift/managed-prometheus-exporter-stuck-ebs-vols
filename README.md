# Stuck EBS Volume Exporter

This monitor is designed to expose a HTTP Service endpoint that Prometheus will use to gather information about the state of the cluster's attached EBS volumes.

## Prometheus Output

A volume may be in one of these states `attaching`, `attached`, `detaching`, `detached` and is thus reported, for example, in one time slice:

        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attaching"} 1.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attached"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detaching"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detached"} 0.0

The next time slice may be

        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attaching"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attached"} 1.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detaching"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detached"} 0.0

And the next might be

        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attaching"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="attached"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detaching"} 0.0
        ebs_volume_state{vol_id="vol-d34db33f",clusterid="testcluster",vol_state="detached"} 1.0

Here, we can see the transition from attaching to attached to detached. Note that the the state record may have missed the `detaching` state transition on the way to `detached` due to the polling interval.

(Note: These are sample outputs)

### PromQL - What's Stuck

When the attaching or detaching state is high (`1.0`) for whichever interval we care about we can consider the volume `vol_id` to be "stuck."

The query `min_over_time(ebs_volume_state{ebs_volume_state="attaching"}[5m]) == 1` can be used to identify volumes which have only been in the `attaching` state for the past five minutes. The `[5m]` time interval can be changed for other timeframes, perhaps causing a warning at 5 minutes and a critical alert at 10 minutes.

## Required IAM Roles

This service requires these read-only IAM roles:

* `ec2:DescribeInstances`
* `ec2:DescribeVolumes`

## Installation Process

Installation of the exporter is a multi-step process. Step one is to use the provided Makefile to render various templates into OpenShift YAML manifests.

### Rendering Templates with Make

A total of four variables must be provided with make:

* `AWS_REGION` - The region to make AWS API calls against
* `AWS_ACCESS_KEY_ID` - The AWS access key ID
* `AWS_SECRET_ACCESS_KEY` - The AWS secret access key
* `CLUSTERID` - The identifier of the cluster. Only EBS volumes with tag `kubernetes.io/cluster/$CLUSTERID` will be checked

Optionally, a different image version can be provided with the `IMAGE_VERSION` variable. The defalt is `stable`.

Currently these are provided as environment variables to `make`.

`make all` will render these manifests:

* `deploy/025_sourcecode.yaml`
* `deploy/030_secrets.yaml`
* `deploy/040_deployment.yaml`

Once these have been created the collection of manifests can be applied in the usual fashion (such as `oc apply -f`).

### Additional Make Targets

The Makefile includes three helpful targets:

* `clean` - Delete any of the rendered manifest files which the Makefile renders
* `filelist` - Echos to the terminal a list of all the YAML files in the `deploy` directory
* `resourcelist` - Echos to the terminal a list of OpenShift/Kubernetes objects created by the manifests in the `deploy` directory, which may be useful for those wishing to delete the installation of this monitor.

### Prometheus Rules

Rules are provided by the [openshift/managed-cluster-config](https://github.com/openshift/managed-cluster-config) repository.
