"""Standard-library client for the scoped Content Factory Hermes API."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused; configure the private API directly')


def settings():
    # Gateway terminal tools need not inherit custom keys from a routed profile.
    # Read only this installed skill's profile, never cwd or global HERMES_HOME.
    keys=('CONTENT_FACTORY_HERMES_URL','CONTENT_FACTORY_HERMES_TOKEN','CONTENT_FACTORY_MEDIA_CACHE')
    values={}
    profile_env=Path(__file__).resolve().parents[3]/'.env'
    if profile_env.is_file():
        for line in profile_env.read_text(encoding='utf-8-sig').splitlines():
            key,sep,value=line.strip().partition('=')
            if sep and key in keys:
                value=value.strip()
                if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):
                    value=value[1:-1]
                values[key]=value
    values.update({key:os.environ[key] for key in keys if key in os.environ})
    return values


def config():
    values=settings()
    url=values.get('CONTENT_FACTORY_HERMES_URL','http://127.0.0.1:18510').rstrip('/')
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Invalid private API base URL')
    token=values.get('CONTENT_FACTORY_HERMES_TOKEN','')
    if len(token)<24:raise ValueError('Private Hermes credential not configured')
    return url,token


def identifier(value):
    if str(uuid.UUID(value))!=value:raise ValueError('Expected canonical UUID')
    return value


def route(args):
    if args.command=='delivery':
        if not re.fullmatch(r'-?[0-9]{1,20}',args.chat_id) or args.message_id < 1:raise ValueError('Invalid message identity')
        return '/deliveries/'+args.chat_id+'/'+str(args.message_id)
    if args.command=='sources':return '/sources'
    if args.command=='ingest':return '/ingest'
    if args.command=='status':return '/jobs/'+identifier(args.job)
    if args.command=='groups':return '/groups'
    if args.command in ('group','select'):
        if not args.group.startswith('source:') or len(args.group)!=71 or any(c not in '0123456789abcdef' for c in args.group[7:]):raise ValueError('Invalid source group')
        return '/groups/'+args.group+('/selection' if args.command=='select' else '')
    path='/jobs/'+identifier(args.job)+'/candidates/'+identifier(args.candidate)
    if args.command=='review':path+='/reviews'
    if args.command=='note':path+='/notes'
    if args.command=='record-delivery':path+='/deliveries'
    if args.command=='media':
        if not args.artifact_id.startswith('sha256:') or len(args.artifact_id)!=71 or any(c not in '0123456789abcdef' for c in args.artifact_id[7:]):raise ValueError('Invalid artifact identity')
        path+='/media?'+urllib.parse.urlencode({'artifact_id':args.artifact_id})
    return path


def run(args):
    url,token=config();path=route(args)
    payload=None
    if args.command in ('review','select','note','ingest','record-delivery'):
        source=Path(args.payload_file)
        if source.stat().st_size>65536:raise ValueError('Action payload too large')
        raw=json.loads(source.read_text(encoding='utf-8-sig'))
        if not isinstance(raw,dict):raise ValueError('Action payload must be an object')
        payload=json.dumps(raw,ensure_ascii=False).encode()
    request=urllib.request.Request(url+'/v2/hermes'+path,data=payload,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    opener=urllib.request.build_opener(NoRedirect())
    checksum=None
    if args.command=='media':
        check=urllib.request.Request(url+'/v2/hermes'+path.split('/media?',1)[0],headers={'Authorization':'Bearer '+token})
        with opener.open(check,timeout=90) as response:
            metadata=json.loads(response.read(65536))
        checksum=metadata.get('master_sha256')
        if metadata.get('artifact_id')!=args.artifact_id or not isinstance(checksum,str) or len(checksum)!=64:
            raise ValueError('Candidate checksum or artifact identity unavailable')
    with opener.open(request,timeout=90) as response:
        if args.command!='media':
            raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise ValueError('Response too large; inspect a smaller source group')
            return json.loads(raw)
        size=int(response.headers.get('Content-Length','0'))
        if not 0<size<=50_000_000 or response.headers.get_content_type()!='video/mp4':raise ValueError('Invalid media response')
        cache=Path(settings().get('CONTENT_FACTORY_MEDIA_CACHE',str(Path.home()/'.cache'/'nopocket-content'))).resolve()
        cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,target=tempfile.mkstemp(prefix='candidate-',suffix='.mp4',dir=cache)
        try:
            total=0
            hasher=hashlib.sha256()
            with os.fdopen(fd,'wb') as stream:
                while chunk:=response.read(65536):
                    total+=len(chunk)
                    if total>size:raise ValueError('Media exceeds declared size')
                    hasher.update(chunk)
                    stream.write(chunk)
            if total!=size:raise ValueError('Incomplete media download')
            if hasher.hexdigest()!=checksum:raise ValueError('Media checksum mismatch')
            return {'local_media_path':target,'bytes':total,'artifact_id':args.artifact_id,
                'delivery_media':metadata.get('delivery_media'),
                'delivery_status':'NOT_SENT','next_step':'Attach using the existing Hermes gateway media tool; application download alone is not Telegram delivery.'}
        except BaseException:
            Path(target).unlink(missing_ok=True)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('groups')
    sub.add_parser('sources')
    p=sub.add_parser('delivery');p.add_argument('--chat-id',required=True);p.add_argument('--message-id',required=True,type=int)
    p=sub.add_parser('ingest');p.add_argument('--payload-file',required=True)
    p=sub.add_parser('status');p.add_argument('--job',required=True)
    for name in ('group','select'):
        p=sub.add_parser(name);p.add_argument('--group',required=True)
        if name=='select':p.add_argument('--payload-file',required=True)
    for name in ('candidate','review','media','note','record-delivery'):
        p=sub.add_parser(name);p.add_argument('--job',required=True);p.add_argument('--candidate',required=True)
        if name in ('review','note','record-delivery'):p.add_argument('--payload-file',required=True)
        if name=='media':p.add_argument('--artifact-id',required=True)
    try:
        result=run(parser.parse_args());print(json.dumps(result,ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        hint={409:'Reload current revision; preserve the shown artifact identity. Historical observations can be saved as notes.',
              422:'Check action schema. REJECTED requires rejection_domain (UNSPECIFIED when the owner did not classify it).'}
        print(json.dumps({'error':'API rejected request','http_status':exc.code,'next_step':hint.get(exc.code,'Check private bridge configuration.')}));raise SystemExit(1)
    except (ValueError,OSError,KeyError) as exc:
        # Do not echo credentials, arbitrary response bodies or source content.
        print(json.dumps({'error':'Editorial action failed','type':type(exc).__name__}));raise SystemExit(1)

if __name__=='__main__':main()
