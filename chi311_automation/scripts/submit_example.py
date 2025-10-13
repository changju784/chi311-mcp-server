"""Example script to POST a sample request to the local MCP server.

Usage: activate venv, install deps, run uvicorn, then:
    python chi311_automation/scripts/submit_example.py

This script assumes the server is running on http://localhost:8000
"""
import json
import urllib.request

url = "http://localhost:8000/mcp/submit_311_request"

payload = {
    "request_type": "aircraft_noise_complaint",
    "location": "200 S Wacker St, Chicago, IL",
    "description": "Large pothole in the right lane",
    "fields": {
        "*1. Which airport or heliport are you registering a noise complaint against?": "Airport - Chicago O'Hare International Airport",
        "*2. What date did the aircraft noise event occur ?": "Oct 10, 2025"
    }
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
