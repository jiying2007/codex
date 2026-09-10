#!/usr/bin/env python3
"""Archive public Yuque documents discovered by the rendered public index."""
import argparse, hashlib, json, mimetypes, os, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from public_knowledge_archive import ArchiveRecord, VisibleTextParser, canonicalize, filename_for, load_existing, markdown_page, safe_output_dir

BOOK_IDS = {"aiui/zzoolv": 20671768, "caixueyang/kb": 24174543}

def text_from_html(html):
    parser = VisibleTextParser(); parser.feed(html)
    return "\n".join(parser.text_parts).strip()

def terminal_failures(index_path):
    if not index_path.exists(): return set()
    return {row.get("canonical_url") for row in (json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()) if row.get("status") in {"api-no-content", "api-error", "access-gated", "unsupported-book", "blocked-domain"}}

def materialize_html(out, url, content):
    assets=out / "assets"; assets.mkdir(parents=True,exist_ok=True); saved=[]
    def store(src):
        if not src.startswith(("http://", "https://")): return None
        if os.environ.get("CODEX_OFFLINE_HERMETIC") == "1": return None
        try:
            response=urlopen(Request(src,headers={"User-Agent":"CodexPublicKnowledgeArchive/0.1 (+public-only; no-auth)"}),timeout=15)
            media=response.headers.get_content_type(); blob=response.read()
            if not media.startswith("image/") or not blob: return None
            digest=hashlib.sha256(blob).hexdigest(); ext=mimetypes.guess_extension(media) or ".img"; name=f"{digest}{ext}"; path=assets / name
            if not path.exists(): path.write_bytes(blob)
            saved.append(name); return f"../assets/{name}"
        except Exception: return None
    def replace(match):
        src=match.group(1)
        local=store(src); return match.group(0).replace(src, local) if local else match.group(0)
    localized=re.sub(r'<img[^>]+src=["\']([^"\']+)["\']', replace, content, flags=re.I)
    for card in re.findall(r'<card[^>]+name="image"[^>]+value="([^"]+)"', localized, flags=re.I):
        try:
            payload=json.loads(unquote(card)[5:]); src=payload.get("src", ""); local=store(src)
            if local: localized=localized.replace(src, local)
        except (ValueError, json.JSONDecodeError): pass
    stem=filename_for(url).replace(".md", ""); rel=f"pages/{stem}.html"; (out / rel).write_text(localized,encoding="utf-8")
    return rel, saved

def main():
    p=argparse.ArgumentParser(description="Archive public Yuque document APIs from a rendered discovery manifest.")
    p.add_argument("--source-manifest", required=True); p.add_argument("--output-dir", required=True)
    p.add_argument("--category", default="yuque-public"); p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--refresh-assets", action="store_true")
    args=p.parse_args()
    if os.environ.get("CODEX_OFFLINE_HERMETIC") == "1": raise SystemExit("network disabled by CODEX_OFFLINE_HERMETIC")
    if not 1 <= args.max_pages <= 100: raise SystemExit("--max-pages must be 1-100")
    out=safe_output_dir(args.output_dir); urls=json.loads(Path(args.source_manifest).read_text(encoding="utf-8")).get("urls", [])
    existing=load_existing(out / "index.jsonl"); records=[]
    terminal=terminal_failures(out / "index.jsonl")
    for raw in urls:
        if len(records)>=args.max_pages: break
        url=canonicalize(raw)
        if url in terminal: continue
        expected_html=out / "pages" / filename_for(url).replace(".md", ".html")
        if url in existing and expected_html.exists() and not args.refresh_assets: continue
        parts=[x for x in urlparse(url).path.split("/") if x]
        now=datetime.now(timezone.utc).isoformat()
        if urlparse(url).hostname not in {"www.yuque.com", "yuque.com"} or len(parts)<3:
            records.append(ArchiveRecord(url,url,"",now,"",0,args.category,0,"blocked-domain",None,"not a discovered Yuque document")); continue
        book_key="/".join(parts[:2]); slug=parts[2]; book_id=BOOK_IDS.get(book_key)
        if not book_id:
            records.append(ArchiveRecord(url,url,"",now,"",0,args.category,0,"unsupported-book",None,book_key)); continue
        api=f"https://www.yuque.com/api/docs/{slug}?include_contributors=true&include_like=true&include_hits=true&merge_dynamic_data=false&book_id={book_id}"
        try:
            data=json.load(urlopen(Request(api,headers={"User-Agent":"CodexPublicKnowledgeArchive/0.1 (+public-only; no-auth)"}),timeout=20)).get("data",{})
            if not data.get("public") or not data.get("allow_public_api_read"):
                records.append(ArchiveRecord(url,url,str(data.get("title", "")),now,"",0,args.category,0,"access-gated",None,"not public API readable")); continue
            text=text_from_html(str(data.get("content", ""))); title=str(data.get("title", "Untitled public document"))
            if not text:
                records.append(ArchiveRecord(url,url,title,now,"",0,args.category,0,"api-no-content",None,"public response has no text")); continue
        except Exception as exc:
            records.append(ArchiveRecord(url,url,"",now,"",0,args.category,0,"api-error",None,str(exc))); continue
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(); rel=f"pages/{filename_for(url)}"; record=ArchiveRecord(url,url,title,now,digest,len(text),args.category,0,"archived",rel,"renderer-discovered; public-api-read")
        (out / "pages").mkdir(parents=True,exist_ok=True); (out / rel).write_text(markdown_page(record,text),encoding="utf-8")
        html_rel, assets=materialize_html(out,url,str(data.get("content", ""))); record.note=f"renderer-discovered; public-api-read; html={html_rel}; assets={len(assets)}"; records.append(record)
    out.mkdir(parents=True,exist_ok=True)
    with (out / "index.jsonl").open("a",encoding="utf-8") as h:
        for record in records: h.write(json.dumps(record.__dict__,ensure_ascii=False,sort_keys=True)+"\n")
    (out / "latest-api-run.json").write_text(json.dumps({"kind":"yuque-public-api-archive-run","retrieved_at":datetime.now(timezone.utc).isoformat(),"source_manifest":args.source_manifest,"records":[r.__dict__ for r in records],"raw_content_stored":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"ok","records":[r.__dict__ for r in records]},ensure_ascii=False))
if __name__ == "__main__": main()
