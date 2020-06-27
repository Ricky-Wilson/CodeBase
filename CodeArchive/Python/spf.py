#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  king_phisher/spf.py
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

import collections
import logging
import re

from king_phisher import ipaddress
from king_phisher import its
from king_phisher.constants import SPFResult

import dns.exception
import dns.name
import dns.query
import dns.rdtypes.ANY.TXT
import dns.resolver
import smoke_zephyr.utilities

MACRO_REGEX = re.compile(r'%\{([slodipvh])(\d*)([r]?)(.?)\}')
"""A regular expression which matches SPF record macros."""

MAX_QUERIES = 10
"""
The maximum number of DNS queries allowed to take place during evaluation as
defined within section 4.6.4 of :rfc:`7208`.
"""
MAX_QUERIES_VOID = float('inf')
"""
The maximum number of DNS queries allowed to either return with rcode 0 and no
answers or rcode 3 (Name Error) as defined within section 4.6.4 of :rfc:`7208`.
"""

DEFAULT_DNS_TIMEOUT = 10
"""
The default number of seconds to wait for a query response from the DNS server.
"""

QUALIFIERS = {
	'+': SPFResult.PASS,
	'-': SPFResult.FAIL,
	'~': SPFResult.SOFT_FAIL,
	'?': SPFResult.NEUTRAL
}
"""A dict object keyed with the qualifier symbols to their readable values."""

SPFMatch = collections.namedtuple('SPFMatch', ('record', 'directive'))
"""A simple container to associate a matched directive with it's record."""

class SPFDirective(object):
	"""
	A class representing a single directive within a sender policy framework
	record.
	"""
	__slots__ = ('mechanism', 'qualifier', 'rvalue')
	def __init__(self, mechanism, qualifier, rvalue=None):
		"""
		:param str mechanism: The SPF mechanism that this directive uses.
		:param str qualifier: The qualifier value of the directive in it's single character format.
		:param str rvalue: The optional rvalue for directives which use them.
		"""
		if qualifier not in QUALIFIERS:
			raise ValueError('invalid qualifier: ' + qualifier)
		self.mechanism = mechanism
		self.qualifier = qualifier
		self.rvalue = rvalue

	def __repr__(self):
		return "<{0} '{1}' >".format(self.__class__.__name__, str(self))

	def __str__(self):
		directive = ''
		if self.qualifier != '+':
			directive += self.qualifier
		directive += self.mechanism
		if self.rvalue:
			directive += ':' + self.rvalue
		return directive

	@classmethod
	def from_string(cls, directive):
		"""
		Parse an SPF directive from a string and return it's class
		representation.

		:param str directive: The SPF directive to parse.
		"""
		if ':' in directive:
			(mechanism, rvalue) = directive.split(':', 1)
		else:
			(mechanism, rvalue) = (directive, None)
		mechanism = mechanism.lower()

		qualifier = '+'
		if mechanism[0] in QUALIFIERS:
			qualifier = mechanism[0]
			mechanism = mechanism[1:]
		return cls(mechanism, qualifier, rvalue)

class SPFRecord(object):
	"""
	A class representing a parsed Sender Policy Framework record with all of
	its directives.
	"""
	__slots__ = ('domain', 'directives')
	def __init__(self, directives, domain=None):
		"""
		:param list directives: A list of :py:class:`.SPFDirective` instances.
		:param str domain: The domain with which this record is associated with.
		"""
		self.directives = directives
		self.domain = domain

	def __repr__(self):
		return "<{0} '{1}' >".format(self.__class__.__name__, str(self))

	def __str__(self):
		return 'v=spf1 ' + ' '.join(str(d) for d in self.directives)

class SPFError(Exception):
	"""Base exception for errors raised by this module."""
	def __init__(self, message):
		self.message = message

	def __repr__(self):
		return "<{0} message='{1}' >".format(self.__class__.__name__, self.message)

class SPFPermError(SPFError):
	"""
	Exception indicating that the domains published records could not be
	correctly interpreted. Described in section 2.6.7 of :rfc:`7208`.
	"""
	pass

class SPFParseError(SPFPermError):
	"""
	Exception indicating that the domains published records could not be
	correctly parsed.
	"""
	pass

class SPFTempError(SPFError):
	"""
	Exception indicating that the verification process encountered a transient
	(generally DNS) error while performing the check. Described in section 2.6.6
	of :rfc:`7208`.
	"""
	pass

class SPFTimeOutError(SPFTempError):
	"""
	Exception indicating that a timeout occurred while querying the DNS server.
	This is normally caused when the client can't communicate with the DNS
	server.
	"""
	pass

@smoke_zephyr.utilities.Cache('3m')
def check_host(ip, domain, sender=None, timeout=DEFAULT_DNS_TIMEOUT):
	"""
	Analyze the Sender Policy Framework of a domain by creating a
	:py:class:`.SenderPolicyFramework` instance and returning the result of
	:py:meth:`.SenderPolicyFramework.check_host`.

	:param ip: The IP address of the host sending the message.
	:type ip: str, :py:class:`ipaddress.IPv4Address`, :py:class:`ipaddress.IPv6Address`
	:param str domain: The domain to check the SPF policy of.
	:param str sender: The "MAIL FROM" identity of the message being sent.
	:param int timeout: The timeout for DNS queries.
	:return: The result of the SPF policy if one can be found or None.
	:rtype: None, str
	"""
	s = SenderPolicyFramework(ip, domain, sender=sender, timeout=timeout)
	return s.check_host()

def validate_record(ip, domain, sender=None):
	"""
	Check if an SPF record exists for the domain and can be parsed by this
	module.

	:return: Whether the record exists and is parsable or not.
	:rtype: bool
	"""
	try:
		result = check_host(ip, domain, sender)
	except SPFPermError:
		return False
	return isinstance(result, str)

# http://tools.ietf.org/html/rfc7208
class SenderPolicyFramework(object):
	"""
	Analyze the Sender Policy Framework configuration for a domain to determine
	if an IP address is authorized to send messages on it's behalf. The exp
	modifier defined in section 6.2 of the RFC is not supported.
	"""
	def __init__(self, ip, domain, sender=None, timeout=DEFAULT_DNS_TIMEOUT):
		"""
		:param ip: The IP address of the host sending the message.
		:type ip: str, :py:class:`ipaddress.IPv4Address`, :py:class:`ipaddress.IPv6Address`
		:param str domain: The domain to check the SPF policy of.
		:param str sender: The "MAIL FROM" identity of the message being sent.
		:param int timeout: The timeout for DNS queries.
		"""
		if isinstance(ip, str):
			ip = ipaddress.ip_address(ip)
		self.ip_address = ip
		self.domain = domain
		self.helo_domain = 'unknown'
		sender = (sender or 'postmaster')
		if not '@' in sender:
			sender = sender + '@' + self.domain
		self.sender = sender
		self.records = collections.OrderedDict()
		"""
		A :py:class:`collections.OrderedDict` of all the SPF records that were
		resolved. This would be any records resolved due to an "include"
		directive in addition to the top level domain.
		"""
		self.matches = []
		"""
		A list of :py:class:`.SPFMatch` instances showing the path traversed to
		identify a matching directive. Multiple entries in this list are
		present when include directives are used and a match is found within
		the body of one. The list is ordered from the top level domain to the
		matching record.
		"""
		# dns lookup limit per https://tools.ietf.org/html/rfc7208#section-4.6.4
		self.query_limit = MAX_QUERIES
		self.query_limit_void = MAX_QUERIES_VOID
		self.policy = None
		self.timeout = timeout
		"""
		The human readable policy result, one of the
		:py:class:`.SPFResult` constants`.
		"""
		self._policy_checked = False
		self.logger = logging.getLogger('KingPhisher.SPF.SenderPolicyFramework')

	def __repr__(self):
		return "<{0} ip='{1}' domain='{2}' sender='{3}' >".format(self.__class__.__name__, self.ip_address, self.domain, self.sender)

	def __str__(self):
		return self.check_host() or ''

	def check_host(self):
		"""
		Check the SPF policy described by the object. The string representing the
		matched policy is returned if an SPF policy exists, otherwise None will
		be returned if no policy is defined.

		:return: The result of the SPF policy described by the object.
		:rtype: None, str
		"""
		if not self._policy_checked:
			self.policy = self._check_host(self.ip_address, self.domain, self.sender)
			self._policy_checked = True
		return self.policy

	def _check_host(self, ip, domain, sender, top_level=True):
		try:
			answers, _ = self._dns_query(domain, 'TXT')
		except SPFTimeOutError:
			raise
		except SPFTempError:
			if not top_level:
				raise
			answers = []
		answers = list(part for part in answers if isinstance(part, dns.rdtypes.ANY.TXT.TXT))

		answers = [part for part in answers if part.strings[0].decode('utf-8').startswith('v=spf1 ')]
		if len(answers) == 0:
			return
		record = ''.join([part.decode('utf-8') for part in answers[0].strings])
		if not record.startswith('v=spf1 '):
			raise SPFParseError('invalid record header')

		raw_directives = record[7:].split(' ')
		raw_directives = tuple(directive for directive in raw_directives if len(directive))
		self.logger.debug("parsing {0:,} directives for domain: {1}".format(len(raw_directives), domain))

		if not len(raw_directives):
			raise SPFParseError('no directives were found')

		directives = []
		for directive in raw_directives:
			if directive.startswith('redirect='):
				if len([r for r in raw_directives if r.endswith('all')]):
					# ignore redirects when all is present per https://tools.ietf.org/html/rfc7208#section-6.1
					self.logger.warning("ignoring redirect modifier to: {0} due to an existing 'all' mechanism".format(domain))
					continue
				directive = directive[9:]
				domain = self.expand_macros(directive, self.ip_address, domain, self.sender)
				self.logger.debug("following redirect modifier to: {0}".format(domain))
				if top_level and len(directives) == 0:
					# treat a single redirect as a new top level
					return self._check_host(ip, domain, sender, top_level=True)
				else:
					result = self._check_host(ip, domain, sender, top_level=False)
					self.logger.debug("top check found matching spf record from redirect to: {0}".format(domain))
					return result

			directive = SPFDirective.from_string(directive)
			if directive.mechanism not in ('a', 'all', 'exists', 'include', 'ip4', 'ip6', 'mx', 'ptr'):
				raise SPFParseError("unknown mechanism type: '{0}'".format(directive.mechanism))
			directives.append(directive)

		record = SPFRecord(directives, domain=domain)
		self.records[domain] = record
		for directive in directives:
			if not top_level and directive.mechanism == 'all':
				break
			if self._evaluate_mechanism(ip, domain, sender, directive.mechanism, directive.rvalue):
				self.matches.insert(0, SPFMatch(record, directive))
				self.logger.debug("{0} check found matching spf directive: '{1}'".format(('top' if top_level else 'recursive'), directive))
				return QUALIFIERS[directive.qualifier]

		self.logger.debug('no directives matched, returning default policy of neutral')
		# default result per https://tools.ietf.org/html/rfc7208#section-4.7
		return SPFResult.NEUTRAL

	def _dns_query(self, qname, qtype):
		# querys all system dns servers
		# returns (answers, additional)
		self.query_limit -= 1
		if self.query_limit < 0:
			raise SPFPermError('DNS query limit reached')
		nameserver = dns.resolver.get_default_resolver().nameservers[0]
		query = dns.message.make_query(qname, qtype)
		# Only query first DNS server https://www.rfc-editor.org/rfc/rfc7208.txt (page 19 last paragraph)
		self.logger.debug("resolving {0:<3} record for {1} using nameserver {2} (remaining queries: {3})".format(qtype, qname, nameserver, self.query_limit))
		try:
			response = dns.query.udp(query, nameserver, self.timeout)
		except dns.exception.Timeout:
			self.logger.warning("dns timeout reached, unable to query: {0} (type: {1}, nameserver: {2})".format(qname, qtype, nameserver))
			raise SPFTimeOutError("DNS timeout reached, unable to query: {0} (type: {1}, nameserver: {2})".format(qname, qtype, nameserver))
		except dns.exception.DNSException:
			self.logger.warning("dns resolution error for: {0} (type: {1}, nameserver: {2})".format(qname, qtype, nameserver))
			raise SPFTempError("DNS resolution error for: {0} (type: {1}, nameserver: {2})".format(qname, qtype, nameserver))

		rcode = response.rcode()
		# check for error codes per https://tools.ietf.org/html/rfc7208#section-5
		if rcode not in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN):
			self.logger.warning("dns resolution error for: {0} (type: {1} rcode: {2})".format(qname, qtype, rcode))
			raise SPFTempError("DNS resolution error for: {0} (type: {1} rcode: {2})".format(qname, qtype, rcode))
		answers = []
		if len(response.answer) == 0 or rcode == dns.rcode.NXDOMAIN:
			self.logger.debug("resolving {0:<3} record for {1} using nameserver {2} resulted in a void lookup".format(qtype, qname, nameserver))
			self.query_limit_void -= 1
			if self.query_limit_void < 0:
				raise SPFPermError('DNS query void lookup limit reached')
		for answer in response.answer:
			answers.extend(answer.items)
		return answers, response.additional

	def _evaluate_mechanism(self, ip, domain, sender, mechanism, rvalue):
		if rvalue is None:
			rvalue = domain
		else:
			rvalue = self.expand_macros(rvalue, ip, domain, sender)

		if mechanism == 'a':
			if self._hostname_matches_ip(ip, rvalue):
				return True
		elif mechanism == 'all':
			return True
		elif mechanism == 'exists':
			answers, _ = self._dns_query(rvalue, 'A')
			if len(answers):
				return True
		elif mechanism == 'include':
			# pass results in match per https://tools.ietf.org/html/rfc7208#section-5.2
			return self._check_host(ip, rvalue, sender, top_level=False) == SPFResult.PASS
		elif mechanism == 'ip4':
			try:
				if its.py_v2 and isinstance(rvalue, str):
					rvalue = rvalue.decode('utf-8')
				ip_network = ipaddress.IPv4Network(rvalue, strict=False)
			except ipaddress.AddressValueError:
				raise SPFParseError('invalid IPv4 network: ' + rvalue)
			if ip in ip_network:
				return True
		elif mechanism == 'ip6':
			try:
				if its.py_v2 and isinstance(rvalue, str):
					rvalue = rvalue.decode('utf-8')
				ip_network = ipaddress.IPv6Network(rvalue, strict=False)
			except ipaddress.AddressValueError:
				raise SPFParseError('invalid IPv6 network: ' + rvalue)
			if ip in ip_network:
				return True
		elif mechanism == 'mx':
			answers, additional = self._dns_query(rvalue, 'MX')
			for answer in answers:
				hostname = None
				if answer.rdtype == dns.rdatatype.MX:
					hostname = answer.exchange
				elif answer.rdtype == dns.rdatatype.CNAME:
					hostname = answer.target
				else:
					raise ValueError('answer is not an MX or CNAME record')
				hostname = str(hostname).rstrip('.')
				found, matches = self._hostname_matches_additional(ip, hostname, additional)
				if matches:
					return True
				if not found and self._hostname_matches_ip(ip, hostname):
					return True
		elif mechanism == 'ptr':
			if isinstance(ip, ipaddress.IPv4Address):
				ip = str(ip)
				suffix = 'in-addr'
			else:
				ip = '.'.join(ip.exploded.replace(':', ''))
				suffix = 'ip6'
			ptr_domain = (rvalue or domain)
			ip = ip.split('.')
			ip.reverse()
			ip = '.'.join(ip)
			answers, _ = self._dns_query(ip + '.' + suffix + '.arpa', 'PTR')
			for ptr_record in answers:
				ptr_record = str(ptr_record.target).rstrip('.')
				if ptr_domain == ptr_record or ptr_domain.endswith('.' + ptr_record):
					return True
		else:
			raise SPFPermError("unsupported mechanism type: '{0}'".format(mechanism))
		return False

	def _hostname_matches_additional(self, ip, name, additional):
		"""
		Search for *name* in *additional* and if it is found, check that it
		includes *ip*.

		:param ip: The IP address to search for.
		:type ip: :py:class:`ipaddress.IPv4Address`, :py:class:`ipaddress.IPv6Address`
		:param str name: The name to search for.
		:param tuple additional: The additional data returned from a dns query to search in.
		:return: The first value is whether or not *name* was found in *additional*, the second is if *ip* was also found.
		:rtype: tuple
		"""
		rdtype = (1 if isinstance(ip, ipaddress.IPv4Address) else 28)
		ip = str(ip)
		additional = (entry for entry in additional if entry.rdtype == rdtype)
		entry = next((entry for entry in additional if str(entry.name)[:-1] == name), None)
		if entry is None:
			return False, None
		item = next((item for item in entry.items if item.address == ip), None)
		return True, item is not None

	def _hostname_matches_ip(self, ip, name):
		qtype = ('A' if isinstance(ip, ipaddress.IPv4Address) else 'AAAA')
		answers, _ = self._dns_query(name, qtype)
		return str(ip) in tuple(a.address for a in answers)

	def expand_macros(self, value, ip, domain, sender):
		"""
		Expand a string based on the macros it contains as specified by section
		7 of :rfc:`7208`.

		:param str value: The string containing macros to expand.
		:param ip: The IP address to use when expanding macros.
		:type ip: str, :py:class:`ipaddress.IPv4Address`, :py:class:`ipaddress.IPv6Address`
		:param str domain: The domain name to use when expanding macros.
		:param str sender: The email address of the sender to use when expanding macros.
		:return: The string with the interpreted macros replaced within it.
		:rtype: str
		"""
		if isinstance(ip, str):
			ip = ipaddress.ip_address(ip)

		macro_table = {
			's': sender,
			'l': sender.split('@', 1)[0],
			'o': sender.split('@', 1)[1],
			'd': domain,
			'i': (str(ip) if isinstance(ip, ipaddress.IPv4Address) else '.'.join(ip.exploded.replace(':', ''))),
			#'p'
			'v': ('in-addr' if isinstance(ip, ipaddress.IPv4Address) else 'ip6'),
			'h': self.helo_domain
		}

		for escape in (('%%', '%'), ('%-', '%20'), ('%_', ' ')):
			value = value.replace(*escape)

		end = 0
		result = ''
		for match in MACRO_REGEX.finditer(value):
			result += value[end:match.start()]
			macro_type = match.group(1)
			macro_digit = int(match.group(2) or 128)
			macro_reverse = (match.group(3) == 'r')
			macro_delimiter = (match.group(4) or '.')

			if not macro_type in macro_table:
				raise SPFPermError("unsupported macro type: '{0}'".format(macro_type))
			macro_value = macro_table[macro_type]
			macro_value = macro_value.split(macro_delimiter)
			if macro_reverse:
				macro_value.reverse()
			macro_value = macro_value[-macro_digit:]
			macro_value = '.'.join(macro_value)

			result += macro_value
			end = match.end()
		result += value[end:]
		return result

	@property
	def match(self):
		if not self.matches:
			return None
		return self.matches[-1]
