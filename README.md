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

> Note: Or save the above environment variables to `.env`.

Translate issues to English:

```bash
bash issues.sh --input=https://github.com/ossrs/srs/issues/3692
```

Translate discussions to English:

```bash
bash discussions.sh --input=https://github.com/orgs/ossrs/discussions/3700
```

Once translated, this tool appends a MAGIC string to the conclusion of the text body to prevent repeated translations.

