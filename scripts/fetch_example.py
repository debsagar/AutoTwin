"""Download the published synthetic purchase-to-pay sample; preserve its timestamps."""
import csv
import gzip
import hashlib
import io
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
import xml.etree.ElementTree as ET

URL = 'https://zenodo.org/records/10435849/files/inputs.zip'
DEST = Path(__file__).resolve().parents[1] / 'data/benchmark/p2p_synthetic.xes'


def main():
    if DEST.exists():
        raise SystemExit(f'Already exists; left unchanged: {DEST}')
    with urlopen(URL, timeout=120) as response:
        archive = response.read()
    if hashlib.md5(archive).hexdigest() != '4328addf237dd05dc631e5e7b341552b':
        raise SystemExit('Source archive changed; check the published version before proceeding.')
    with ZipFile(io.BytesIO(archive)) as bundle:
        rows = list(csv.DictReader(io.StringIO(gzip.decompress(
            bundle.read('synthetic/Procure_to_Pay.csv.gz')).decode('utf-8-sig'))))
    log = ET.Element('log', {'xes.version': '1.0'})
    traces = {}
    for row in rows:
        case = row['case_id']
        if case not in traces:
            traces[case] = ET.SubElement(log, 'trace')
            ET.SubElement(traces[case], 'string', key='concept:name', value=case)
        event = ET.SubElement(traces[case], 'event')
        for tag, key, column in [('string', 'concept:name', 'activity'),
                                 ('string', 'org:resource', 'resource'),
                                 ('date', 'start_timestamp', 'start_time'),
                                 ('date', 'time:timestamp', 'end_time')]:
            value = row[column].replace(' ', 'T') if tag == 'date' else row[column]
            ET.SubElement(event, tag, key=key, value=value)
    assert len(traces) == 1000 and len(rows) == 13290, 'Unexpected sample size'
    DEST.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(log).write(DEST, encoding='utf-8', xml_declaration=True)
    print(f'{DEST}: {len(traces)} cases, {len(rows)} events')


if __name__ == '__main__':
    main()
