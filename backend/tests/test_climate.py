import copy
import hashlib
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path
import httpx
import pytest
from app.ingestion.climate.client import Client
from app.ingestion.climate.extract import extract, from_batch
from app.ingestion.climate.transform import transform
from app.ingestion.climate.validate import selection, rainfall
from app.climate.service import daily_series, accumulations


@pytest.fixture
def climate():
    root=Path(__file__).parent/'fixtures'
    return (root/'inmet-a237.csv').read_bytes(),json.loads((root/'inmet-a237-manifest.json').read_text(encoding='utf8'))


def change(content, meta, old, new):
    content=content.replace(old.encode('latin1'),new.encode('latin1'))
    meta=copy.deepcopy(meta);meta['raw_sha256']=hashlib.sha256(content).hexdigest()
    return content,meta


def test_official_identity_coordinates_units_interval_and_provenance(climate):
    station,rows,report=transform(*climate)
    assert station['official_code']=='A237' and station['name']=='CAXIAS'
    assert station['latitude']==-4.82138888 and station['longitude']==-43.3436111
    assert len(rows)==24 and report['complete_days']==1 and report['rejected']==[]
    assert rows[0]['measured_at'].isoformat()=='2025-01-01T01:00:00+00:00'
    assert rows[-1]['measured_at'].isoformat()=='2025-01-02T00:00:00+00:00'
    assert rows[0]['value_mm']==0 and rows[0]['availability']=='OBSERVED'
    assert rows[0]['source_metadata']['interval_start']=='2025-01-01T00:00:00+00:00'
    assert rows[0]['source_metadata']['original_unit']=='mm'
    assert rows[0]['source_metadata']['quality_status']=='NOT_PROVIDED'
    assert rows[0]['source_metadata']['eligible_for_risk'] is False
    assert report['daily'][0]['value_mm'] is not None and len(report['daily'][0]['contributor_ids'])==24


@pytest.mark.parametrize('old,new',[
 ('A237','A312'), ('Hora UTC','Hora local'), ('HORÁRIO (mm)','HORÁRIO (cm)'),
 ('LATITUDE:;-4,82138888','LATITUDE:;100'), ('REGIAO:','REGION:'),
])
def test_bad_contract_identity_coordinate_unit(climate,old,new):
    with pytest.raises(ValueError):transform(*change(*climate,old,new))


@pytest.mark.parametrize('raw',['-1','NaN','Infinity','bad','10000000','0,00001'])
def test_invalid_values_rejected(raw):
    with pytest.raises(ValueError):rainfall(raw)


@pytest.mark.parametrize('raw',['','-9999','-9999,0'])
def test_missing_distinct_from_zero(raw):
    assert rainfall(raw) is None and rainfall('0')==0


def test_missing_rejected_dates_and_duplicates(climate):
    b,m=climate
    # Alter only the chosen precipitation cell, keep every official field around it.
    line=b.decode('latin1').splitlines()[10]
    fields=line.split(';'); fields[2]=''
    _,rows,report=transform(*change(b,m,line,';'.join(fields)))
    assert report['missing_values']==1 and report['complete_days']==0
    assert report['daily'][0]['value_mm'] is None
    fields[2]='-1'
    _,_,report=transform(*change(b,m,line,';'.join(fields)))
    assert len(report['rejected'])==1 and report['accepted']==23
    assert report['daily'][0]['value_mm'] is None
    _,_,report=transform(*change(b,m,'2025/01/01;0100 UTC','2025/02/30;0100 UTC'))
    assert len(report['rejected'])==1
    dup=b+b'\n'+line.encode('latin1')+b'\n';dm=copy.deepcopy(m);dm['raw_sha256']=hashlib.sha256(dup).hexdigest()
    _,_,report=transform(dup,dm)
    assert report['duplicates']==1 and report['accepted']==24
    fields[2]='10'
    conflict=dup+';'.join(fields).encode('latin1')+b'\n';dm['raw_sha256']=hashlib.sha256(conflict).hexdigest()
    _,_,report=transform(conflict,dm)
    assert len(report['rejected'])==3 and report['accepted']==23


def test_absent_interval_and_no_data(climate):
    b,m=climate;line=b.decode('latin1').splitlines()[10]
    _,_,report=transform(*change(b,m,line,''))
    assert report['absent_or_rejected_intervals']==1 and report['daily'][0]['value_mm'] is None
    empty=b'\n'.join(b.splitlines()[:9])+b'\n';m=copy.deepcopy(m);m['raw_sha256']=hashlib.sha256(empty).hexdigest()
    with pytest.raises(ValueError):transform(empty,m)


@pytest.mark.parametrize('station,start,end',[('X','2025-01-01','2025-03-31'),('A237','2025-03-31','2025-01-01'),('A237','2025-01-01','2026-01-01'),('A237','2025-12-31','2025-12-31'),('A237','bad','2025-01-01')])
def test_incompatible_periods(station,start,end):
    with pytest.raises(ValueError):selection(station,start,end)


def test_accumulations_require_every_day(climate):
    _,rows,_=transform(*climate)
    full=[]
    for offset in range(90):
        for r in rows:
            row=copy.deepcopy(r); row['measured_at']+=timedelta(days=offset);full.append(row)
    daily=daily_series(full,date(2025,1,1),date(2025,3,31))
    result=accumulations(daily,date(2025,3,31))
    assert all(v['status']=='AVAILABLE' for v in result.values())
    assert result['90']['complete_days']==90
    full.pop()
    result=accumulations(daily_series(full,date(2025,1,1),date(2025,3,31)),date(2025,3,31))
    assert all(v['status']=='INSUFFICIENT_DATA' and v['value_mm'] is None for v in result.values())
    assert accumulations(daily,date(2025,1,3))['7']['value_mm'] is None


def test_duplicate_interval_never_summed(climate):
    _,rows,_=transform(*climate)
    daily=daily_series(rows+[rows[0]],date(2025,1,1),date(2025,1,1))
    assert daily[0]['value_mm'] is None and daily[0]['ambiguous_hours']==1


def test_checksum_and_metadata_protected(climate):
    b,m=climate
    with pytest.raises(ValueError):transform(b+b'x',m)
    for key,val in [('source','OTHER'),('unit','cm'),('timezone','UNKNOWN'),('batch',''),('source_url','https://other.test'),('extracted_at','2025-01-01T00:00:00')]:
        meta=copy.deepcopy(m);meta[key]=val
        with pytest.raises(ValueError):transform(b,meta)


def test_extract_original_zip_immutable_batches_and_checksum(tmp_path,climate):
    b,m=climate; archive=tmp_path/'official.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(m['archive_member'],b)
    raw=tmp_path/'raw'
    first=extract(None,raw,station='A237',start='2025-01-01',end='2025-01-01',file=archive)
    second=extract(None,raw,station='A237',start='2025-01-01',end='2025-01-01',file=archive)
    assert first[1]['batch']!=second[1]['batch']
    folder=raw/first[1]['batch']; assert from_batch(folder)==first
    (folder/'station.csv').write_bytes(b+b'x')
    with pytest.raises(ValueError,match='Checksum'):from_batch(folder)


@pytest.mark.parametrize('status',[403,404,429,500])
def test_http_errors_no_bypass(tmp_path,status,monkeypatch):
    monkeypatch.setattr('app.ingestion.climate.client.time.sleep',lambda _:None)
    calls=[]
    def respond(request):
        calls.append(request);return httpx.Response(status,request=request)
    with pytest.raises(httpx.HTTPStatusError):Client(httpx.Client(transport=httpx.MockTransport(respond))).download(2025,tmp_path/'result.zip')
    assert len(calls)==(3 if status>=500 else 1)


def test_timeout_and_empty_response(tmp_path,monkeypatch):
    monkeypatch.setattr('app.ingestion.climate.client.time.sleep',lambda _:None)
    def timeout(request):raise httpx.ReadTimeout('timeout',request=request)
    with pytest.raises(httpx.ReadTimeout):Client(httpx.Client(transport=httpx.MockTransport(timeout))).download(2025,tmp_path/'empty.zip')
    with pytest.raises(ValueError,match='vazia'):Client(httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,request=r)))).download(2025,tmp_path/'empty.zip')


def test_unexpected_archive_and_extraction_failure_report(tmp_path):
    archive=tmp_path/'bad.zip';archive.write_text('HTML protection page')
    with pytest.raises(zipfile.BadZipFile):extract(None,tmp_path/'raw',station='A237',start='2025-01-01',end='2025-01-01',file=archive)
    assert len(list((tmp_path/'raw').glob('*/failure.json')))==1


def test_successful_http_extract_and_download_limit(tmp_path,climate,monkeypatch):
    import io
    b,m=climate
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:z.writestr(m['archive_member'],b)
    original=stream.getvalue()
    client=Client(httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=original,headers={'Content-Type':'application/zip'},request=r))))
    content,meta=extract(client,tmp_path/'raw',station='A237',start='2025-01-01',end='2025-01-01')
    assert content==b and meta['acquisition']=='official_http_download'
    assert meta['response_headers']['content-type']=='application/zip'
    assert from_batch(tmp_path/'raw'/meta['batch'])[0]==b
    monkeypatch.setattr('app.ingestion.climate.client.MAX_BYTES',5)
    with pytest.raises(ValueError,match='limite'):client.download(2025,tmp_path/'too-large.zip')
