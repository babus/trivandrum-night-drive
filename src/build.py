#!/usr/bin/env python3
"""Splice citydata.json into drive.html, write ../index.html and a .gz beside it.

The page is ~14 MB of which almost all is JSON, and JSON compresses about 4:1.
serve.py hands out the .gz when the client advertises gzip, so a phone on WiFi
downloads roughly 3 MB instead of 14.
"""
import gzip
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'index.html')

HEAD = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    '<style>*{margin:0;padding:0}</style>\n</head>\n<body>\n'
)
TAIL = '\n</body>\n</html>\n'


def main():
    html = open(os.path.join(HERE, 'drive.html'), encoding='utf-8').read()
    data = open(os.path.join(HERE, 'citydata.json'), encoding='utf-8').read()
    # '<' can't appear outside a JSON string, so escaping it everywhere is safe and
    # stops any name containing "</script" from closing the tag early.
    data = data.replace('<', '\\u003c')

    if '/*__CITYDATA__*/' not in html:
        raise SystemExit('drive.html is missing the /*__CITYDATA__*/ placeholder')

    page = HEAD + html.replace('/*__CITYDATA__*/', data) + TAIL
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(page)

    raw = os.path.getsize(OUT)
    with open(OUT, 'rb') as src, gzip.open(OUT + '.gz', 'wb', compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)
    gz = os.path.getsize(OUT + '.gz')

    print('index.html     %6.2f MB' % (raw / 1048576))
    print('index.html.gz  %6.2f MB  (%.1fx smaller)' % (gz / 1048576, raw / gz))


if __name__ == '__main__':
    main()
