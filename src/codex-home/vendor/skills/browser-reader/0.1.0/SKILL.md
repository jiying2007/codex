---
name: browser-reader
description: Use when the user asks to open or read a webpage with a real browser, inspect a page after manual verification, handle anti-bot pages such as WeChat public account articles, capture page evidence, or says "浏览器查看", "打开网页读取", "微信公众号文章整理", "agent-browser", or "需要浏览器". This is a constrained read-only workflow that may use agent-browser when available; it must not bypass captcha, log in automatically, submit forms, or scrape at scale.
version: 0.1.0
last_updated: 2026-05-10
---

# Browser Reader

Use this skill for user-authorized browser reading when normal HTTP fetch cannot access the content.

## Good Fits

- WeChat public account articles that return environment verification pages
- Pages requiring JavaScript rendering
- User manually completes a captcha or safety check, then asks Codex to summarize visible content
- Screenshot or DOM evidence collection for a single page

## Hard Boundaries

- Do not bypass captchas or anti-bot checks.
- Do not auto-login, enter credentials, or submit forms.
- Do not access private pages unless the user explicitly authorizes the exact page.
- Do not bulk crawl or mirror content.
- Do not claim content was read if only a verification page was accessible.

## Workflow

1. Try the least invasive method first:
   - Use normal web/open or HTTP fetch if available.
   - If it returns a verification page, say that plainly.
2. If browser access is needed:
   - Use `agent-browser` only as a read-only helper.
   - Ask the user to complete any captcha or account verification manually.
   - After verification, read only the visible page or user-approved DOM.
3. Extract:
   - Title
   - Publisher/source
   - Date if visible
   - Main points
   - Evidence snippets within copyright limits
   - Original URL
4. If the result should be retained, route to `knowledge-archive`.

## WeChat Public Account Notes

For `mp.weixin.qq.com`:

- A redirect to `/mp/wappoc_appmsgcaptcha` means WeChat returned a security verification page.
- In that state, do not attempt automated bypass.
- Tell the user to open the link in a trusted local browser or WeChat and complete verification.
- Then summarize the user-visible article content if browser tooling can access it.

## Output

Report:

- Whether content or only a verification page was reachable
- Browser/manual verification status
- Extracted summary, if available
- Source URL
- Any follow-up archive path if saved
