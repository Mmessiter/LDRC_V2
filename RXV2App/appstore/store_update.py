import json, subprocess, sys, urllib.request, urllib.error
APP='6789857533'; OLD='d4ebdc78-9cce-4c3c-a306-95c7089f97bf'; BUILD='b0df7402-a97e-4314-9241-e1aaf6faac8a'; VER='5.173'
WHATS_NEW=("Safer firmware updates: the app waits for the receiver's WiFi, will not start while the transmitter is on, "
           "and never runs its background backup during an update.\n"
           "Reviews open as the right model and now show Travel extents, Ports and Black box.\n"
           "The Rates and PIDs pages follow your transmitter's bank switch (never over unsaved edits).\n"
           "Easy tuning sliders work with the Actual rates type.\n"
           "New: Compare models - your rates side by side with another model's backup.\n"
           "The Rates help explains how each rates type works.")
def token():
    return subprocess.check_output(['python3','appstore/asc_token.py','KLS4GZ93JB','69a6de80-5be5-47e3-e053-5b8c7c11a4d1']).decode().strip()
T=token()
def req(method, path, body=None):
    r=urllib.request.Request('https://api.appstoreconnect.apple.com'+path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+T,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=60) as f: t=f.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        d=json.loads(e.read() or b'{}'); d['_status']=e.code; return d
def die(msg, d=None):
    print('STOP:', msg); 
    if d: print(json.dumps(d.get('errors', d))[:800])
    sys.exit(1)

old=req('GET', f'/v1/appStoreVersions/{OLD}?include=appStoreReviewDetail,appStoreVersionLocalizations')
oa=old['data']['attributes']
orev=next((i['attributes'] for i in old.get('included',[]) if i['type']=='appStoreReviewDetails'), None)
oloc=next((i['attributes'] for i in old.get('included',[]) if i['type']=='appStoreVersionLocalizations'), None)
if not orev or not oloc: die('old version lacks review detail or localization')

# 1. the new version (reuse one left from an earlier attempt)
vs=req('GET', f'/v1/apps/{APP}/appStoreVersions?filter[versionString]={VER}&filter[platform]=IOS')
if vs.get('data'): NEW=vs['data'][0]['id']; print('reusing version', VER, NEW)
else:
    attrs={'platform':'IOS','versionString':VER,'releaseType':oa.get('releaseType') or 'AFTER_APPROVAL'}
    if oa.get('copyright'): attrs['copyright']=oa['copyright']
    d=req('POST','/v1/appStoreVersions',{'data':{'type':'appStoreVersions','attributes':attrs,
        'relationships':{'app':{'data':{'type':'apps','id':APP}},'build':{'data':{'type':'builds','id':BUILD}}}}})
    if 'data' not in d: die('create version', d)
    NEW=d['data']['id']; print('created version', VER, NEW)
# make sure the build is attached
b=req('GET', f'/v1/appStoreVersions/{NEW}/build')
if not (b.get('data') and b['data']['id']==BUILD):
    d=req('PATCH', f'/v1/appStoreVersions/{NEW}/relationships/build', {'data':{'type':'builds','id':BUILD}})
    if d.get('_status',204) >= 300: die('attach build', d)
print('build 443 attached')

# 2. text: localization + What's New
locs=req('GET', f'/v1/appStoreVersions/{NEW}/appStoreVersionLocalizations').get('data',[])
loc=next((l for l in locs if l['attributes']['locale']==oloc['locale']), None)
if not loc:
    a={k:oloc.get(k) for k in ['locale','description','keywords','promotionalText','supportUrl','marketingUrl'] if oloc.get(k)}
    d=req('POST','/v1/appStoreVersionLocalizations',{'data':{'type':'appStoreVersionLocalizations','attributes':a,
        'relationships':{'appStoreVersion':{'data':{'type':'appStoreVersions','id':NEW}}}}})
    if 'data' not in d: die('create localization', d)
    loc=d['data']; print('localization created')
d=req('PATCH', f"/v1/appStoreVersionLocalizations/{loc['id']}", {'data':{'type':'appStoreVersionLocalizations','id':loc['id'],'attributes':{'whatsNew':WHATS_NEW}}})
if 'data' not in d: die('whatsNew', d)
print("What's New set")

# 3. review details (notes with the Bluetooth video link)
rv=req('GET', f'/v1/appStoreVersions/{NEW}/appStoreReviewDetail')
fields={k:orev.get(k) for k in ['contactFirstName','contactLastName','contactPhone','contactEmail','demoAccountRequired','notes']}
if rv.get('data'):
    d=req('PATCH', f"/v1/appStoreReviewDetails/{rv['data']['id']}", {'data':{'type':'appStoreReviewDetails','id':rv['data']['id'],'attributes':fields}})
else:
    d=req('POST','/v1/appStoreReviewDetails',{'data':{'type':'appStoreReviewDetails','attributes':fields,
        'relationships':{'appStoreVersion':{'data':{'type':'appStoreVersions','id':NEW}}}}})
if 'data' not in d: die('review details', d)
print('review notes copied (', len(fields['notes'] or ''), 'ch )')

# 4. preflight: screenshots present, build fit to ship
ss=req('GET', f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets?include=appScreenshots")
nsets=len(ss.get('data',[])); nshots=len([i for i in ss.get('included',[]) if i['type']=='appScreenshots'])
print('screenshots:', nsets, 'sets,', nshots, 'images')
if nshots == 0: die('no screenshots on the new version - copy them before submitting')
bb=req('GET', f'/v1/builds/{BUILD}')['data']['attributes']
print('build', bb['version'], bb['processingState'], '| non-exempt encryption:', bb.get('usesNonExemptEncryption'))
if bb['processingState']!='VALID': die('build not valid')

# 5. submit
if '--submit' not in sys.argv: print('DRY RUN complete - everything present'); sys.exit(0)
s=req('POST','/v1/reviewSubmissions',{'data':{'type':'reviewSubmissions','attributes':{'platform':'IOS'},
      'relationships':{'app':{'data':{'type':'apps','id':APP}}}}})
if 'data' not in s: die('open submission', s)
SID=s['data']['id']; print('submission', SID)
d=req('POST','/v1/reviewSubmissionItems',{'data':{'type':'reviewSubmissionItems','relationships':{
      'reviewSubmission':{'data':{'type':'reviewSubmissions','id':SID}},'appStoreVersion':{'data':{'type':'appStoreVersions','id':NEW}}}}})
if 'data' not in d: die('add version to submission', d)
d=req('PATCH', f'/v1/reviewSubmissions/{SID}', {'data':{'type':'reviewSubmissions','id':SID,'attributes':{'submitted':True}}})
if 'data' not in d: die('submit', d)
print('SUBMITTED | state:', d['data']['attributes'].get('state'), '| submission', SID)
