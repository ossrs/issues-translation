# issues-translation

[![](https://badgen.net/discord/members/yZ4BnPmHAd)](https://discord.gg/yZ4BnPmHAd)

Use AI/GPT to translate GitHub issues into English.

## Usage

Setup OpenAI API key and GitHub token:

```bash
export GITHUB_TOKEN=xxx
export OPENAI_API_KEY=xxx
export OPENAI_PROXY=xxx
```

> Note: The `GITHUB_TOKEN` is required to update the issue ,please read [Authenticating to the REST API](https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api) to create one.

> Note: The `OPENAI_API_KEY` is required, which is the API key for OpenAI API.

> Note: The OPENAI_PROXY is optional, which is the proxy for OpenAI API.

Start a venv and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Translate issues to English:

```bash
python issues.py --issue=https://github.com/ossrs/srs/issues/3692
```

