
'''
Retrive the title from a webpage.
'''
import sys
from urllib.request import urlopen
from html.parser import HTMLParser


class TitleParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.match = False
        self.title = ''

    def handle_starttag(self, tag, attributes):
        self.match = True if tag == 'title' else False

    def handle_data(self, data):
        if self.match:
            self.title = data
            self.match = False


def get_title(src, timeout=0.30):
    # Prefix HTTP protocol if iter
    # does not exist.
    if not src.startswith('http://'):
        src = 'http://' + src
    parser = TitleParser()
    try:
        parser.feed(str(urlopen(src, timeout=timeout).read()))
        return parser.title
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error:
        #print(error)
        pass



