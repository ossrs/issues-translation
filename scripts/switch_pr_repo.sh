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
v5=no
v6=no
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
    echo "  --v5          Whether merge to 5.0"
    echo "  --v6          Whether merge to 6.0"
    echo "  --v7          Whether merge to 7.0"
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

echo "remote=${remote}, branch=${branch}, v5=${v5}, v6=${v6}, v7=${v7}"

if [[ $v5 == no && $v6 == no && $v7 == no ]]; then
  echo "Please specify the version by --v5 or --v6 or --v7"
  exit 1
fi

cd $SRS_HOME &&
echo "Switch to SRS_HOME $SRS_HOME OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to SRS_HOME $SRS_HOME failed, ret=$ret"; exit $ret; fi

TARGET_BRANCH=develop
if [[ $v5 == yes && $v6 == no && $v7 == no ]]; then
  TARGET_BRANCH=5.0release
elif [[ $v5 == no && $v6 == yes && $v7 == no ]]; then
  TARGET_BRANCH=6.0release
fi

git checkout $TARGET_BRANCH &&
echo "Switch to branch $TARGET_BRANCH OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to branch $TARGET_BRANCH failed, ret=$ret"; exit $ret; fi

git pull &&
echo "Pull $TARGET_BRANCH OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Pull $TARGET_BRANCH failed, ret=$ret"; exit $ret; fi

git remote remove $PR_REPO 2>/dev/null || echo "Remove $PR_REPO not exists, OK" &&
REMOTE_URL="git@github.com:$remote.git" &&
git remote add $PR_REPO $REMOTE_URL &&
echo "Add remote $PR_REPO $REMOTE_URL OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Add remote $PR_REPO $REMOTE_URL failed, ret=$ret"; exit $ret; fi

git fetch $PR_REPO &&
echo "Fetch remote $PR_REPO"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Fetch remote $PR_REPO failed, ret=$ret"; exit $ret; fi

TMP_BRANCH=pr-$branch &&
git branch -D $TMP_BRANCH $PR_REPO/$branch 2>/dev/null || echo "Branch $TMP_BRANCH not exists, OK" &&
git checkout -b $TMP_BRANCH $PR_REPO/$branch &&
echo "Switch to branch $TMP_BRANCH track $remote $branch OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Switch to branch $TMP_BRANCH track $remote $branch failed, ret=$ret"; exit $ret; fi

git merge --no-edit $TARGET_BRANCH &&
echo "Merge $TARGET_BRANCH to branch $TMP_BRANCH OK"
ret=$?; if [[ 0 -ne $ret ]]; then echo "Merge $TARGET_BRANCH to branch $TMP_BRANCH failed, ret=$ret"; exit $ret; fi

echo "OK"
