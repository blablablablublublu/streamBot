#!/bin/bash
pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn==0.30.1
echo "Installed packages:"
pip list
echo "Uvicorn version:"
pip show uvicorn