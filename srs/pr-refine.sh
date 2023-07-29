#!/bin/bash

# Execute by: bash xxx.sh or bash zzz/yyy/xxx.sh or ./xxx.sh or ./zzz/yyy/xxx.sh source xxx.sh
REALPATH=$(realpath ${BASH_SOURCE[0]})
SCRIPT_DIR=$(cd $(dirname ${REALPATH}) && pwd)
WORK_DIR=$(cd $(dirname ${REALPATH})/.. && pwd)
echo "BASH_SOURCE=${BASH_SOURCE}, REALPATH=${REALPATH}, SCRIPT_DIR=${SCRIPT_DIR}, WORK_DIR=${WORK_DIR}"
cd ${WORK_DIR}

help=no
input=
token=
proxy=
key=
v5=
v6=

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) help=yes; shift ;;
        --input) input=$2; shift 2;;
        --token) token=$2; shift 2;;
        --proxy) proxy=$2; shift 2;;
        --key) key=$2; shift 2;;
        --v5) v5=$2; shift 2;;
        --v6) v6=$2; shift 2;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
done

if [[ "$help" == yes ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help    Show this help message and exit"
    echo "  --input       The url of pr, for example, GitHub PR URL, for example, https://github.com/your-org/your-repository/pull/3699"
    echo "  --v5          Whether merge to v5 branch"
    echo "  --v6          Whether merge to v6 branch"
    echo "  --token       (Optional) GitHub access token, for example, github_pat_xxx_yyyyyy"
    echo "  --proxy       (Optional) OpenAI API proxy, for example, x.y.z"
    echo "  --key         (Optional) OpenAI API key, for example, xxxyyyzzz"
    exit 0
fi

if [[ -z $input ]]; then
    echo "Error: --input is empty"
    exit 1
fi

if [[ -z $v5 && -z $v6 ]]; then
    echo "Error: --v5 and --v6 are empty"
    exit 1
fi

. venv/bin/activate
ret=$?; if [[ $ret != 0 ]]; then echo "Activate venv failed"; exit $ret; fi

PARAMS="--input $input"
if [[ ! -z $token ]]; then
    PARAMS="$PARAMS --token $token"
fi
if [[ ! -z $proxy ]]; then
    PARAMS="$PARAMS --proxy $proxy"
fi
if [[ ! -z $key ]]; then
    PARAMS="$PARAMS --key $key"
fi

echo -e "\n\n\n\n\n\n"
echo "========================================================================"
echo "==== python pr-trans.py $PARAMS"
echo "========================================================================"
python pr-trans.py $PARAMS
ret=$?; if [[ $ret != 0 ]]; then echo "Translate pr failed"; exit $ret; fi

echo -e "\n\n\n\n\n\n"
echo "========================================================================"
echo "==== python pr-rephrase.py $PARAMS"
echo "========================================================================"
python pr-rephrase.py $PARAMS
ret=$?; if [[ $ret != 0 ]]; then echo "Rephrase pr failed"; exit $ret; fi

if [[ ! -z $v5 ]]; then
    PARAMS="$PARAMS --v5 $v5"
fi
if [[ ! -z $v6 ]]; then
    PARAMS="$PARAMS --v6 $v6"
fi
echo -e "\n\n\n\n\n\n"
echo "========================================================================"
echo "==== python pr-release-update.py $PARAMS"
echo "========================================================================"
python pr-release-update.py $PARAMS
ret=$?; if [[ $ret != 0 ]]; then echo "Update release of pr failed"; exit $ret; fi


echo -e "\n\n\n\n\n\n"
echo "========================================================================"
echo "==== OK!"
echo "========================================================================"
