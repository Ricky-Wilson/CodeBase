import requests
import sys
import socket


def get_server_name(src, timeout=0.30):
	'''
    Obtaine the name of a webserver via http HEAD
    request.
    '''
	try:
		return requests.head(src, timeout=timeout).headers.get('server')
	except KeyboardInterrupt:
		sys.exit(0)
	except Exception:
		# TODO log errors
		pass


def hyperlink(src, name):
	# Assume the src is a ip addr
	# if it does not start with "http"
	# and fix it.
	if not src.startswith('http'):
		src = 'http://' + src
	return '<a href="{}">{}</a>'.format(src, name)


def get_hostname(ip):
	try:
		return socket.gethostbyaddr(ip)
	except KeyboardInterrupt:
		sys.exit(0)
	except:
		pass


server = get_server_name('https://209.194.29.146')
hostname = get_hostname('209.194.29.146')

print(hyperlink('209.194.29.146', server))
