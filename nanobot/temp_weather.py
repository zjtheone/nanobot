#!/usr/bin/env python3
import urllib.request

url = "https://wttr.in/Beijing?format=3"
response = urllib.request.urlopen(url, timeout=10)
print(response.read().decode())
