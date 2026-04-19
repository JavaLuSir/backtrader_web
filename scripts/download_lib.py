import urllib.request
urls = [
    ("https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js", "D:/backtrader_web/static/highlight.min.js"),
    ("https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js", "D:/backtrader_web/static/python.min.js"),
]
for url, path in urls:
    try:
        urllib.request.urlretrieve(url, path)
        print(f"OK: {path}")
    except Exception as e:
        print(f"Error: {e}")