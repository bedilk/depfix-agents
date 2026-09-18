"""HTML changelog feed for dated API-version announcements."""
from __future__ import annotations
import hashlib,re
from typing import Any,ClassVar
import httpx
from depfix.sources.base import ChangeSource
from depfix.sources.models import ChangeEvent,FeedPoll,FeedStateSnapshot,Severity,SourceKind
class ChangelogHtmlSource(ChangeSource):
    kind:ClassVar[SourceKind]=SourceKind.CHANGELOG_HTML
    def __init__(self,provider_id:str,config:dict[str,Any],http:httpx.Client):
        super().__init__(provider_id,config);self.url=self._require("url");self._http=http
    @property
    def feed_key(self)->str:return f"changelog_html:{self.url}"
    def poll(self,state:FeedStateSnapshot)->FeedPoll:
        try:r=self._http.get(self.url)
        except httpx.HTTPError as exc:return FeedPoll.failure(f"fetch failed: {exc}")
        if r.status_code==404:return FeedPoll.missing("changelog URL 404")
        if r.status_code>=400:return FeedPoll.failure(f"HTTP {r.status_code}")
        digest=hashlib.sha256(r.content).hexdigest(); versions=sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b",r.text)),reverse=True)
        if not versions:return FeedPoll.baseline(state.last_token or "unknown",sha=digest)
        newest=versions[0]
        if state.last_token is None:return FeedPoll.baseline(newest,sha=digest)
        if newest==state.last_token:return FeedPoll.unchanged(token=newest,sha=digest)
        text=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text));index=text.find(newest);body=text[max(0,index-500):index+1500]
        return FeedPoll(changed=True,new_token=newest,payload_sha256=digest,events=[ChangeEvent(provider_id=self.provider_id,feed_key=self.feed_key,source_kind=self.kind,source_url=self.url,old_token=state.last_token,new_token=newest,title=f"{self.provider_id} API version {newest}",summary=f"New dated API version: {newest}",body=body,severity=Severity.POTENTIALLY_BREAKING if any(x in body.lower() for x in ("breaking","removed","deprecated","migration")) else Severity.UNKNOWN)])
