#FROM ubuntu:focal
FROM python:3.9-bullseye

ADD . /usr/local/issues-translation

WORKDIR /usr/local/issues-translation

RUN rm -rf venv .env .git .idea && \
  python3 -m venv venv && \
  . venv/bin/activate && \
  pip install -r requirements.txt

EXPOSE 2023

ENTRYPOINT ["/usr/local/issues-translation/scripts/entrypoint.sh"]
