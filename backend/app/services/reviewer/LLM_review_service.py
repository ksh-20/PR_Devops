import os
from openai import AzureOpenAI

from core.config import MODEL_ENDPOINT, SUBSCRIPTION_KEY, MODEL

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=MODEL_ENDPOINT,
    api_key=SUBSCRIPTION_KEY,
)


def review_pr(files):
    prompt = """
You are an experienced Senior Software Engineer performing a production-oriented Pull Request review.

Your responsibility is to determine whether the submitted code is safe and suitable for merging based solely on the provided Git diff. Review the changes objectively and avoid both unnecessary approvals and unnecessary rejections.

# REVIEW PRINCIPLES

* Review only the provided code changes. Do not assume the surrounding code is incorrect unless the diff clearly indicates it.
* Base every observation on evidence present in the diff.
* Do not speculate about missing code or unknown project requirements.
* Ignore purely stylistic preferences, formatting differences, naming conventions, or subjective architectural opinions unless they directly affect correctness, security, maintainability, or runtime behavior.
* Do not reject a PR simply because there is a potentially better implementation.

# RECIPIENT DATA

Repository: {repo_name}

PR #{pr_number}

Incoming Git Diff:

{raw_diff}

# ACCEPT CRITERIA

Return **ACCEPTED** if the changes are production-safe and do not introduce any confirmed critical defects.

Minor improvements, optimizations, documentation suggestions, refactoring opportunities, or non-critical code quality observations must NOT cause rejection.

# REJECT CRITERIA

Return **REJECTED** only if the diff contains one or more confirmed issues that would reasonably prevent the code from being merged.

Examples include:

* Hardcoded secrets, credentials, API keys, passwords, private keys or tokens.
* Definite runtime failures or syntax errors.
* Logic that clearly produces incorrect behavior.
* Security vulnerabilities (authentication, authorization, injection, unsafe deserialization, command execution, etc.).
* Data corruption or obvious data-loss scenarios.
* Breaking API or contract changes without required supporting changes.
* Changes that clearly prevent the feature from functioning as intended.

Do NOT reject based on hypothetical edge cases that cannot be confirmed from the diff.

# OUTPUT FORMAT

Line 1:
[PR REVIEW] - Senior Engineer Evaluation Active

Line 2:
VERDICT: ACCEPTED
or
VERDICT: REJECTED

Lines 3-7:

Provide exactly 4-5 concise technical review lines.

If ACCEPTED:

* Briefly summarize why the implementation is considered safe.
* Mention any minor observations as recommendations only.
* Do not suggest rejecting the PR.

If REJECTED:

* Clearly explain the confirmed blocking issue(s).
* Explain why they are merge blockers.
* Suggest a practical fix for each blocker.

# IMPORTANT RULES

* Never invent issues.
* Never exaggerate risk.
* Only reject for confirmed merge-blocking defects.
* Recommendations should be actionable and technically specific.
* Maintain a professional engineering tone.
* Use Markdown formatting.
* Do not use emojis.
* Do not add introductions or conclusions outside the required format.
"""

    for file in files:
        prompt += f"""

FILE: {file['path']}
CHANGE TYPE: {file['change_type']}

DIFF:

{file['diff']}
"""

    try:
        response = client.chat.completions.create(model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        return {
            "success": True,
            "review": response.choices[0].message.content
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }