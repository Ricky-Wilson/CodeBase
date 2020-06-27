from apport.hookutils import *
from os import path
import distro
import webbrowser

if distro.id() == 'debian':
	community_support = "https://www.debian.org/support"
else:
	community_support = "https://www.ubuntu.com/support/community-support"

def add_info(report, ui):
    if report['ProblemType'] == 'Crash':
        return

    response = ui.choice("How would you describe the issue?", ["I'm having problems with the Help Browser.", "I need help performing a Task."], False)
    if response == None:
        raise StopIteration
    if response == [0]: # bug on the documentation or yelp
        return
    # user is requesting help rather than having a bug.
    ui.information("Since you're requesting help rather than having a bug on the application please visit a suitable support resource: %s. Thanks in advance." % community_support)
    webbrowser.open(community_support)
    raise StopIteration
