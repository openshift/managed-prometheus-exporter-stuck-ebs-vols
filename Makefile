SHELL := /bin/bash

# All of the source files which compose the monitor. 
# Important note: No directory structure will be maintained
SOURCEFILES ?= monitor/main.py monitor/start.sh

INIT_IMAGE_VERSION ?= 1903.0.0
IMAGE_VERSION ?= stable

RESOURCELIST := servicemonitor/stuck-ebs-vols service/stuck-ebs-vols \
	deployment/stuck-ebs-vols secret/stuck-ebs-vols-credentials-volume \
	configmap/stuck-ebs-vols-code rolebinding/sre-stuck-ebs-vols \
	serviceaccount/sre-stuck-ebs-vols clusterrole/sre-allow-read-cluster-setup \
	rolebinding/sre-stuck-ebs-vols-read-cluster-setup CredentialsRequest/stuck-ebs-vols-aws-credentials \
	secrets/stuck-ebs-vols-aws-credentials

all: deploy/025_sourcecode.yaml deploy/040_deployment.yaml

deploy/025_sourcecode.yaml: $(SOURCEFILES)
	@for sfile in $(SOURCEFILES); do \
		files="--from-file=$$sfile $$files" ; \
	done ; \
	kubectl -n openshift-monitoring create configmap stuck-ebs-vols-code --dry-run=true -o yaml $$files 1> deploy/025_sourcecode.yaml

deploy/040_deployment.yaml: resources/040_deployment.yaml.tmpl
	@sed \
		-e "s/\$$IMAGE_VERSION/$(IMAGE_VERSION)/g" \
		-e "s/\$$INIT_IMAGE_VERSION/$(INIT_IMAGE_VERSION)/g" \
	resources/040_deployment.yaml.tmpl 1> deploy/040_deployment.yaml

.PHONY: clean
clean:
	rm -f deploy/025_sourcecode.yaml deploy/040_deployment.yaml

.PHONY: filelist
filelist: all
	@ls -1 deploy/*.y*ml

.PHONE: resourcelist
resourcelist:
	@echo $(RESOURCELIST)