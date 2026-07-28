# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

This project is in its initial stage — there is no source code, build system, or tests yet. As real code is added, expand this file with the actual build/lint/test commands and architecture.

## Configuration

- `.env` — holds `openrouter_api_key` for authenticating with the [OpenRouter](https://openrouter.ai) API. Do **not** commit this file; add it to `.gitignore` before the first commit.
- `googlegemma.txt` — names the target model: `google/gemma-4-26b-a4b-it:free`, served via OpenRouter.

## Intended direction (inferred, unconfirmed)

The presence of an OpenRouter API key plus a Gemma model identifier suggests this will be an application that calls Google's Gemma model through OpenRouter's API. Confirm and replace this section once the implementation exists.
