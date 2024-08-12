#!/bin/bash

# Execute by: bash xxx.sh or bash zzz/yyy/xxx.sh or ./xxx.sh or ./zzz/yyy/xxx.sh source xxx.sh
REALPATH=$(realpath ${BASH_SOURCE[0]})
SCRIPT_DIR=$(cd $(dirname ${REALPATH}) && pwd)
WORK_DIR=$(cd $(dirname ${REALPATH})/.. && pwd)
echo "BASH_SOURCE=${BASH_SOURCE}, REALPATH=${REALPATH}, SCRIPT_DIR=${SCRIPT_DIR}, WORK_DIR=${WORK_DIR}"
cd ${WORK_DIR}

SRS_HOME=~/git/srs
PR_PREFIX=https://github.com/ossrs/srs/pull
echo "SRS_HOME=${SRS_HOME}, PR_PREFIX=${PR_PREFIX}"

help=no
v5=no
v6=no
v7=no
pr=
title=

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) help=yes; shift ;;
        --v5) v5=yes; shift ;;
        --v6) v6=yes; shift ;;
        --v7) v7=yes; shift ;;
        --pr) pr=$2; shift 2;;
        --title) title=$2; shift 2;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
done

if [[ "$help" == yes ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help    Show this help message and exit"
    echo "  --v5          Whether merge PR to 5.0. Default: no"
    echo "  --v6          Whether merge PR to 6.0. Default: no"
    echo "  --v7          Whether merge PR to 7.0. Default: no"
    echo "  --pr          The GitHub pr number."
    echo "  --title       The GitHub pr title."
    exit 0
fi

if [[ -z $pr ]]; then
    echo "Please specify the pr number by --pr-number"
    exit 1
fi

if [[ -z $title ]]; then
    echo "Please specify the pr title by --title"
    exit 1
fi

echo "v5=${v5}, v6=${v6}, v7=${v7}"

function update_changelog() {
    VERSION=$1
    echo "Update changelog for version $VERSION"

    REVISION=$(cat $SRS_HOME/trunk/src/core/srs_core_version${VERSION}.hpp |grep VERSION_REVISION |awk '{print $3}')
    let NEXT=$REVISION+1
    echo "Last revision is $REVISION, next is $NEXT"

    cat $SRS_HOME/trunk/src/core/srs_core_version${VERSION}.hpp |sed "s/VERSION_REVISION    ${REVISION}/VERSION_REVISION    ${NEXT}/g" > $SRS_HOME/trunk/src/core/srs_core_version${VERSION}.hpp.tmp &&
    mv $SRS_HOME/trunk/src/core/srs_core_version${VERSION}.hpp.tmp $SRS_HOME/trunk/src/core/srs_core_version${VERSION}.hpp
    ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to update version"; exit $ret; fi

    COMMIT_MESSAGE="$COMMIT_MESSAGE v${VERSION}.0.${NEXT}"
    MESSAGE="* v${VERSION}.0, $(date +"%Y-%m-%d"), Merge [#${pr}](${PR_PREFIX}/${pr}): ${title}. v${VERSION}.0.${NEXT} (#${pr})" &&
    echo "MESSAGE=${MESSAGE}"
    ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to make message"; exit $ret; fi

    awk -v pattern="## SRS ${VERSION}.0 Changelog" -v new_line="${MESSAGE}"  '{
        print
        if ($0 ~ pattern) {
            print new_line
        }
    }' $SRS_HOME/trunk/doc/CHANGELOG.md > $SRS_HOME/trunk/doc/CHANGELOG.md.tmp &&
    mv $SRS_HOME/trunk/doc/CHANGELOG.md.tmp $SRS_HOME/trunk/doc/CHANGELOG.md &&
    echo "Update CHANGELOG.md ok"
    ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to update CHANGELOG.md"; exit $ret; fi
}

COMMIT_MESSAGE="Update release to"
if [[ $v5 == yes ]]; then
  update_changelog 5
  echo "Update changelog for version 5 ok"
fi

if [[ $v6 == yes ]]; then
  update_changelog 6
  echo "Update changelog for version 6 ok"
fi

if [[ $v7 == yes ]]; then
  update_changelog 7
  echo "Update changelog for version 6 ok"
fi
echo $COMMIT_MESSAGE >&2

if [[ $v5 == no && $v6 == no && $v7 == no ]]; then
  echo "Please specify the version by --v5 or --v6 or --v7"
  exit 1
fi

cd $SRS_HOME &&
echo "Change dir to $SRS_HOME OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to change dir to $SRS_HOME"; exit $ret; fi

git commit -am "$COMMIT_MESSAGE" &&
echo "Commit $COMMIT_MESSAGE OK"
ret=$?; if [[ $ret -ne 0 ]]; then echo "Failed to commit $COMMIT_MESSAGE"; exit $ret; fi

echo "OK"
