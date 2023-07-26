#!/bin/bash

# Execute by: bash xxx.sh or bash zzz/yyy/xxx.sh or ./xxx.sh or ./zzz/yyy/xxx.sh source xxx.sh
REALPATH=$(realpath ${BASH_SOURCE[0]})
SCRIPT_DIR=$(cd $(dirname ${REALPATH}) && pwd)
WORK_DIR=$(cd $(dirname ${REALPATH})/.. && pwd)
echo "BASH_SOURCE=${BASH_SOURCE}, REALPATH=${REALPATH}, SCRIPT_DIR=${SCRIPT_DIR}, WORK_DIR=${WORK_DIR}"
cd ${WORK_DIR}

SRS_HOME=~/git/srs
echo "SRS_HOME=${SRS_HOME}"

help=no
remote=
branch=

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) help=yes; shift ;;
        --v5) v5=yes; shift ;;
        --v6) v6=yes; shift ;;
        --remote) remote=$2; shift 2;;
        --branch) branch=$2; shift 2;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
done

if [[ "$help" == yes ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help    Show this help message and exit"
    echo "  --remote      The remote respository of pr, for example, winlinvip/srs"
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
echo "Switch to SRS_HOME $SRS_HOME OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to SRS_HOME $SRS_HOME failed, ret=$ret"; exit $ret; fi

git checkout develop &&
echo "Switch to branch develop OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to branch develop failed, ret=$ret"; exit $ret; fi

git remote remove tmp 2>/dev/null || echo "Remove tmp not exists, OK" &&
REMOTE_URL="git@github.com:$remote.git" &&
git remote add tmp $REMOTE_URL &&
echo "Add remote tmp $REMOTE_URL OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Add remote tmp $REMOTE_URL failed, ret=$ret"; exit $ret; fi

git fetch tmp &&
echo "Fetch remote tmp"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Fetch remote tmp failed, ret=$ret"; exit $ret; fi

TMP_BRANCH=pr-$branch &&
git branch -D $TMP_BRANCH tmp/$branch 2>/dev/null || echo "Branch $TMP_BRANCH not exists, OK" &&
git checkout -b $TMP_BRANCH tmp/$branch &&
echo "Switch to branch $TMP_BRANCH track $remote $branch OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to branch $TMP_BRANCH track $remote $branch failed, ret=$ret"; exit $ret; fi

git merge --no-edit develop &&
echo "Merge develop to branch $TMP_BRANCH OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Merge develop to branch $TMP_BRANCH failed, ret=$ret"; exit $ret; fi

echo "OK"
