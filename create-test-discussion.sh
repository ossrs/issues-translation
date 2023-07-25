#!/bin/bash

# Execute by: bash xxx.sh or bash zzz/yyy/xxx.sh or ./xxx.sh or ./zzz/yyy/xxx.sh source xxx.sh
REALPATH=$(realpath ${BASH_SOURCE[0]})
SCRIPT_DIR=$(cd $(dirname ${REALPATH}) && pwd)
WORK_DIR=$(cd $(dirname ${REALPATH}) && pwd)
echo "BASH_SOURCE=${BASH_SOURCE}, REALPATH=${REALPATH}, SCRIPT_DIR=${SCRIPT_DIR}, WORK_DIR=${WORK_DIR}"
cd ${WORK_DIR}

if [[ -f ${WORK_DIR}/.env ]]; then source ${WORK_DIR}/.env; fi
if [[ ! -z $GITHUB_TOKEN ]]; then export GITHUB_TOKEN=$GITHUB_TOKEN; fi

source venv/bin/activate
echo "python create-test-discussion.py $@"
python create-test-discussion.py $@
deactivate
