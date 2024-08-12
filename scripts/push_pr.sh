#!/bin/bash

# Execute by: bash xxx.sh or bash zzz/yyy/xxx.sh or ./xxx.sh or ./zzz/yyy/xxx.sh source xxx.sh
REALPATH=$(realpath ${BASH_SOURCE[0]})
SCRIPT_DIR=$(cd $(dirname ${REALPATH}) && pwd)
WORK_DIR=$(cd $(dirname ${REALPATH})/.. && pwd)
echo "BASH_SOURCE=${BASH_SOURCE}, REALPATH=${REALPATH}, SCRIPT_DIR=${SCRIPT_DIR}, WORK_DIR=${WORK_DIR}"
cd ${WORK_DIR}

SRS_HOME=~/git/srs
PR_REPO=pr-tmp
echo "SRS_HOME=${SRS_HOME}, PR_REPO=${PR_REPO}"

help=no
remote=
branch=

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) help=yes; shift ;;
        --v5) v5=yes; shift ;;
        --v6) v6=yes; shift ;;
        --v7) v7=yes; shift ;;
        --remote) remote=$2; shift 2;;
        --branch) branch=$2; shift 2;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
done

if [[ "$help" == yes ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help    Show this help message and exit"
    echo "  --remote      The remote respository name of pr, for example, winlinvip/srs"
    echo "  --branch      The remote branch of pr, for example, feature/ai-translate"
    exit 0
fi

if [[ -z $remote ]]; then
    echo "Please specify the remote respository by --remote"
    exit 1
fi

if [[ -z $branch ]]; then
    echo "Please specify the remote branch by --branch"
    exit 1
fi

echo "remote=${remote}, branch=${branch}"

cd $SRS_HOME &&
echo "Change dir to $SRS_HOME OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to change dir to $SRS_HOME"; exit $ret; fi

REMOTE_NAME=$(git remote -v |grep $PR_REPO |grep "$remote" |grep push |awk '{print $1}') &&
echo "Get remote name $REMOTE_NAME of $remote OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to get remote name $REMOTE_NAME of $remote"; exit $ret; fi

git push $REMOTE_NAME pr-${branch}:${branch} &&
echo "Push to $REMOTE_NAME pr-${branch}:${branch} OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to push to $REMOTE_NAME pr-${branch}:${branch}"; exit $ret; fi

git checkout develop &&
git branch -D pr-${branch} &&
echo "Delete local branch pr-${branch} OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to delete local branch pr-${branch}"; exit $ret; fi

echo "OK"
