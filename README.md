# issues-translation

[![](https://badgen.net/discord/members/yZ4BnPmHAd)](https://discord.gg/yZ4BnPmHAd)

Use AI/GPT to translate GitHub issues into English.

## Usage

Use docker to translate issue:

```bash
docker run --rm -it -e GITHUB_TOKEN=xxx -e OPENAI_API_KEY=xxx -e OPENAI_PROXY=xxx ossrs/issues-translation:v1 \
  python issue-trans.py --input https://github.com/your-org/your-repository/issues/3692
```

Use docker to translate discussion:

```bash
docker run --rm -it -e GITHUB_TOKEN=xxx -e OPENAI_API_KEY=xxx -e OPENAI_PROXY=xxx ossrs/issues-translation:v1 \
  python discussion-trans.py --input https://github.com/your-org/your-repository/discussions/3700
```

Use docker to translate PR:

```bash
docker run --rm -it -e GITHUB_TOKEN=xxx -e OPENAI_API_KEY=xxx -e OPENAI_PROXY=xxx ossrs/issues-translation:v1 \
  python pr-trans.py --input https://github.com/your-org/your-repository/pull/3699
```

Run GitHub webhooks server:

```bash
docker run --rm -it -e GITHUB_TOKEN=xxx -e OPENAI_API_KEY=xxx -e OPENAI_PROXY=xxx ossrs/issues-translation:v1 \
  python server.py --listen 2023 --forward https://discord.com/xxx
```

Also you can use `--env-file=$(pwd)/.env` to load the environment variables from file `.env`.

## Developer

Write a `.env` file to setup OpenAI API key and GitHub token:

```bash
#.env
GITHUB_TOKEN=xxx
OPENAI_API_KEY=xxx
OPENAI_PROXY=xxx
```

> Note: The `GITHUB_TOKEN` is required to update the issue ,please read [Authenticating to the REST API](https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api) to create one.

> Note: The `OPENAI_API_KEY` is required, which is the API key for OpenAI API.

> Note: The OPENAI_PROXY is optional, which is the proxy for OpenAI API.

> Note: Or save the above environment variables to `.env`.

For fist run, create venv then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Translate issues to English:

```bash
python issue-trans.py --input https://github.com/your-org/your-repository/issues/3692
```

Translate issues to English:

```bash
python pr-trans.py --input https://github.com/your-org/your-repository/pull/3699
python pr-rephrase.py --input https://github.com/your-org/your-repository/pull/3699
```

Translate discussions to English:

```bash
python discussion-trans.py --input https://github.com/your-org/your-repository/discussions/3700
```

Once translated, this tool appends a MAGIC string to the conclusion of the text body to prevent repeated translations.

