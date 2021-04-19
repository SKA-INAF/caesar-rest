#!/bin/bash

CONFIG_FILE=$1

# - Create broker & DB persistent volumes
kubectl --kubeconfig $CONFIG_FILE apply -f pvc-db.yaml
kubectl --kubeconfig $CONFIG_FILE apply -f pvc-broker.yaml

# - Deploy DB pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest-db.yaml

# - Deploy broker pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest-broker.yaml

# - Deploy app pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest.yaml

# - Deploy beat pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest-beat.yaml

# - Deploy beat worker pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest-beat-worker.yaml

# - Deploy worker pod
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-rest-worker.yaml

# - Deploy ingress 
kubectl --kubeconfig $CONFIG_FILE apply -f caesar-ingress.yaml

