#!/usr/bin/env python3

from flask import Flask, url_for, render_template
import os
from flask import *
import fnmatch

app = Flask(__name__)


def index():
    return url_for('static', 'index.html')


app.run(debug=1)