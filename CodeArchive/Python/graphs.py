#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  king_phisher/client/graphs.py
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
import string

from king_phisher import color
from king_phisher import geoip
from king_phisher import its
from king_phisher import ua_parser
from king_phisher import utilities
from king_phisher.client import gui_utilities
from king_phisher.client.widget import extras
from king_phisher.client.widget import managers
from king_phisher.constants import ColorHexCode

from gi.repository import Gtk
from smoke_zephyr.requirements import check_requirements
from smoke_zephyr.utilities import unique

try:
	import matplotlib
	matplotlib.rcParams['backend'] = 'GTK3Cairo'
	from matplotlib import dates
	from matplotlib import patches
	from matplotlib import pyplot
	from matplotlib import ticker
	from matplotlib import lines
	from matplotlib.backends.backend_gtk3cairo import FigureCanvasGTK3Cairo as FigureCanvas
	from matplotlib.backends.backend_gtk3cairo import FigureManagerGTK3Cairo as FigureManager
	from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar
except ImportError:
	has_matplotlib = False
	"""Whether the :py:mod:`matplotlib` module is available."""
else:
	has_matplotlib = True

try:
	import mpl_toolkits.basemap
except ImportError:
	has_matplotlib_basemap = False
	"""Whether the :py:mod:`mpl_toolkits.basemap` module is available."""
else:
	if not its.frozen and check_requirements(['basemap>=1.0.7']):
		has_matplotlib_basemap = False
	else:
		has_matplotlib_basemap = True

EXPORTED_GRAPHS = {}
MPL_COLOR_NULL = 'darkcyan'
PERCENT_FORMAT = '.3g'

__all__ = ('export_graph_provider', 'get_graph', 'get_graphs', 'CampaignGraph')

def _matrices_add(mat1, mat2):
	if not len(mat1) == len(mat2):
		raise RuntimeError('len(mat1) != len(mat2)')
	return [mat1[i] + mat2[i] for i in range(len(mat1))]

def export_graph_provider(cls):
	"""
	Decorator to mark classes as valid graph providers. This decorator also sets
	the :py:attr:`~.CampaignGraph.name` attribute.

	:param class cls: The class to mark as a graph provider.
	:return: The *cls* parameter is returned.
	"""
	if not issubclass(cls, CampaignGraph):
		raise RuntimeError("{0} is not a subclass of CampaignGraph".format(cls.__name__))
	if not cls.is_available:
		return None
	graph_name = cls.__name__[13:]
	cls.name = graph_name
	EXPORTED_GRAPHS[graph_name] = cls
	return cls

def get_graph(graph_name):
	"""
	Return the graph providing class for *graph_name*. The class providing the
	specified graph must have been previously exported using
	:py:func:`.export_graph_provider`.

	:param str graph_name: The name of the graph provider.
	:return: The graph provider class.
	:rtype: :py:class:`.CampaignGraph`
	"""
	return EXPORTED_GRAPHS.get(graph_name)

def get_graphs():
	"""
	Get a list of all registered graph providers.

	:return: All registered graph providers.
	:rtype: list
	"""
	return sorted(EXPORTED_GRAPHS.keys())

class GraphBase(object):
	"""
	A basic graph provider for using :py:mod:`matplotlib` to create graph
	representations of campaign data. This class is meant to be subclassed
	by real providers.
	"""
	name = 'Unknown'
	"""The name of the graph provider."""
	name_human = 'Unknown'
	"""The human readable name of the graph provider used for UI identification."""
	graph_title = 'Unknown'
	"""The title that will be given to the graph."""
	is_available = True
	def __init__(self, application, size_request=None, style_context=None):
		"""
		:param tuple size_request: The size to set for the canvas.
		"""
		self.logger = logging.getLogger('KingPhisher.Client.Graph.' + self.__class__.__name__[13:])
		self.application = application
		self.style_context = style_context
		self.config = application.config
		"""A reference to the King Phisher client configuration."""
		self.figure, _ = pyplot.subplots()
		self.figure.set_facecolor(self.get_color('bg', ColorHexCode.WHITE))
		self.axes = self.figure.get_axes()
		self.canvas = FigureCanvas(self.figure)
		self.manager = None
		self.minimum_size = (380, 200)
		"""An absolute minimum size for the canvas."""
		if size_request is not None:
			self.resize(*size_request)
		self.canvas.mpl_connect('button_press_event', self.mpl_signal_canvas_button_pressed)
		self.canvas.show()
		self.navigation_toolbar = NavigationToolbar(self.canvas, self.application.get_active_window())

		self.popup_menu = managers.MenuManager()
		self.popup_menu.append('Export', self.signal_activate_popup_menu_export)
		self.popup_menu.append('Refresh', self.signal_activate_popup_refresh)

		menu_item = Gtk.CheckMenuItem.new_with_label('Show Toolbar')
		menu_item.connect('toggled', self.signal_toggled_popup_menu_show_toolbar)
		self._menu_item_show_toolbar = menu_item
		self.popup_menu.append_item(menu_item)

		self.navigation_toolbar.hide()
		self._legend = None

	@property
	def rpc(self):
		return self.application.rpc

	@staticmethod
	def _ax_hide_ticks(ax):
		for tick in ax.yaxis.get_major_ticks():
			tick.tick1On = False
			tick.tick2On = False

	@staticmethod
	def _ax_set_spine_color(ax, spine_color):
		for pos in ('top', 'right', 'bottom', 'left'):
			ax.spines[pos].set_color(spine_color)

	def add_legend_patch(self, legend_rows, fontsize=None):
		if matplotlib.__version__ == '3.0.2':
			self.logger.warning('skipping legend patch with matplotlib v3.0.2 for compatibility')
			return
		if self._legend is not None:
			self._legend.remove()
			self._legend = None
		fontsize = fontsize or self.fontsize_scale
		legend_bbox = self.figure.legend(
			tuple(patches.Patch(color=patch_color) for patch_color, _ in legend_rows),
			tuple(label for _, label in legend_rows),
			borderaxespad=1.25,
			fontsize=fontsize,
			frameon=True,
			handlelength=1.5,
			handletextpad=0.75,
			labelspacing=0.3,
			loc='lower right'
		)
		legend_bbox.legendPatch.set_linewidth(0)
		self._legend = legend_bbox

	def get_color(self, color_name, default):
		"""
		Get a color by its style name such as 'fg' for foreground. If the
		specified color does not exist, default will be returned. The underlying
		logic for this function is provided by
		:py:func:`~.gui_utilities.gtk_style_context_get_color`.

		:param str color_name: The style name of the color.
		:param default: The default color to return if the specified one was not found.
		:return: The desired color if it was found.
		:rtype: tuple
		"""
		color_name = 'theme_color_graph_' + color_name
		sc_color = gui_utilities.gtk_style_context_get_color(self.style_context, color_name, default)
		return (sc_color.red, sc_color.green, sc_color.blue)

	def make_window(self):
		"""
		Create a window from the figure manager.

		:return: The graph in a new, dedicated window.
		:rtype: :py:class:`Gtk.Window`
		"""
		if self.manager is None:
			self.manager = FigureManager(self.canvas, 0)
		self.navigation_toolbar.destroy()
		self.navigation_toolbar = self.manager.toolbar
		self._menu_item_show_toolbar.set_active(True)
		window = self.manager.window
		window.set_transient_for(self.application.get_active_window())
		window.set_title(self.graph_title)
		return window

	@property
	def fontsize_scale(self):
		scale = self.markersize_scale
		if scale < 5:
			fontsize = 'xx-small'
		elif scale < 7:
			fontsize = 'x-small'
		elif scale < 9:
			fontsize = 'small'
		else:
			fontsize = 'medium'
		return fontsize

	@property
	def markersize_scale(self):
		bbox = self.axes[0].get_window_extent().transformed(self.figure.dpi_scale_trans.inverted())
		return bbox.width * self.figure.dpi * 0.01

	def mpl_signal_canvas_button_pressed(self, event):
		if event.button != 3:
			return
		self.popup_menu.menu.popup(None, None, None, None, event.button, Gtk.get_current_event_time())
		return True

	def signal_activate_popup_menu_export(self, action):
		dialog = extras.FileChooserDialog('Export Graph', self.application.get_active_window())
		file_name = self.config['campaign_name'] + '.png'
		response = dialog.run_quick_save(file_name)
		dialog.destroy()
		if not response:
			return
		destination_file = response['target_path']
		self.figure.savefig(destination_file, dpi=200, facecolor=self.figure.get_facecolor(), format='png')

	def signal_activate_popup_refresh(self, event):
		self.refresh()

	def signal_toggled_popup_menu_show_toolbar(self, widget):
		if widget.get_property('active'):
			self.navigation_toolbar.show()
		else:
			self.navigation_toolbar.hide()

	def resize(self, width=0, height=0):
		"""
		Attempt to resize the canvas. Regardless of the parameters the canvas
		will never be resized to be smaller than :py:attr:`.minimum_size`.

		:param int width: The desired width of the canvas.
		:param int height: The desired height of the canvas.
		"""
		min_width, min_height = self.minimum_size
		width = max(width, min_width)
		height = max(height, min_height)
		self.canvas.set_size_request(width, height)

class CampaignGraph(GraphBase):
	"""
	Graph format used for the graphs generated in the dashboard and
	in the create graphs tab.
	"""
	def _load_graph(self, info_cache):
		raise NotImplementedError()

	def load_graph(self):
		"""Load the graph information via :py:meth:`.refresh`."""
		self.refresh()

	def refresh(self, info_cache=None, stop_event=None):
		"""
		Refresh the graph data by retrieving the information from the
		remote server.

		:param dict info_cache: An optional cache of data tables.
		:param stop_event: An optional object indicating that the operation should stop.
		:type stop_event: :py:class:`threading.Event`
		:return: A dictionary of cached tables from the server.
		:rtype: dict
		"""
		info_cache = (info_cache or {})
		if not self.rpc:
			return info_cache
		if stop_event and stop_event.is_set():
			return info_cache
		if not info_cache:
			info_cache = self._get_graphql_campaign_cache(self.config['campaign_id'])
		for ax in self.axes:
			ax.clear()
		if self._legend is not None:
			self._legend.remove()
			self._legend = None
		self._load_graph(info_cache)
		self.figure.suptitle(
			self.graph_title,
			color=self.get_color('fg', ColorHexCode.BLACK),
			size=14,
			weight='bold',
			y=0.97
		)
		self.canvas.draw()
		return info_cache

	def _get_graphql_campaign_cache(self, campaign_id):
		options = {'campaign': campaign_id}
		results = self.rpc.graphql("""\
		query getCampaignGraphing($campaign: String!) {
			db {
				campaign(id: $campaign) {
					name
					description
					expiration
					messages {
						total
						edges {
							node {
								id
								targetEmail
								firstName
								lastName
								opened
								openerIp
								openerUserAgent
								sent
								trained
								companyDepartment {
									id
									name
								}
							}
						}
					}
					visits {
						total
						edges {
							node {
								id
								messageId
								campaignId
								count
								ip
								ipGeoloc {
									city
									continent
									coordinates
									country
									postalCode
									timeZone
								}
								firstSeen
								lastSeen
								userAgent
							}
						}
					}
					credentials {
						total
						edges {
							node {
								id
								visitId
								messageId
								campaignId
								username
								password
								submitted
							}
						}
					}
				}
			}
		}""", options)
		info_cache = {
			'campaign': {
				'name': results['db']['campaign']['name'],
				'description': results['db']['campaign']['description'],
				'expiration': results['db']['campaign']['expiration'],
			},
			'messages': results['db']['campaign']['messages'],
			'visits': results['db']['campaign']['visits'],
			'credentials': results['db']['campaign']['credentials']
		}
		return info_cache

class CampaignBarGraph(CampaignGraph):
	subplot_adjustment = {'top': 0.9, 'right': 0.85, 'bottom': 0.05, 'left': 0.225}
	yticklabel_config = {
		'left': {'size': 10},
		'right': {'format': "{0:,}", 'size': 12}
	}
	def __init__(self, *args, **kwargs):
		super(CampaignBarGraph, self).__init__(*args, **kwargs)
		self.figure.subplots_adjust(**self.subplot_adjustment)
		ax = self.axes[0]
		ax.tick_params(
			axis='both',
			top=False,
			right=False,
			bottom=False,
			left=False,
			labelbottom=False
		)
		ax.invert_yaxis()
		self.axes.append(ax.twinx())

	def _barh_stacked(self, ax, bars, bar_colors, height):
		"""
		:param ax: This axis to use for the graph.
		:param tuple bars: A two dimensional array of bars, and their respective stack sizes.
		:param tuple bar_colors: A one dimensional array of colors for each of the stacks.
		:param float height: The height of the bars.
		:return:
		"""
		# define the necessary colors
		ax.set_facecolor(self.get_color('bg', ColorHexCode.WHITE))
		self.resize(height=60 + 20 * len(bars))

		bar_count = len(bars)
		columns = []
		left_subbars = [0] * bar_count
		columns.extend(zip(*bars))
		for right_subbars, color, in zip(columns, bar_colors):
			bar_container = ax.barh(
				range(len(bars)),
				right_subbars,
				color=color,
				height=height,
				left=left_subbars,
				linewidth=0,
			)
			left_subbars = _matrices_add(left_subbars, right_subbars)
		return bar_container

	def _load_graph(self, info_cache):
		raise NotImplementedError()

	def _graph_null_bar(self, title):
		return self.graph_bar([0], [''], xlabel=title)

	def graph_bar(self, bars, yticklabels, xlabel=None):
		"""
		Create a horizontal bar graph with better defaults for the standard use
		cases.

		:param list bars: The values of the bars to graph.
		:param list yticklabels: The labels to use on the x-axis.
		:param str xlabel: The label to give to the y-axis.
		:return: The bars created using :py:mod:`matplotlib`
		:rtype: `matplotlib.container.BarContainer`
		"""
		largest = (max(bars) if len(bars) else 0)
		bars = [[cell, largest - cell] for cell in bars]
		bar_colors = (self.get_color('bar_fg', ColorHexCode.BLACK), self.get_color('bar_bg', ColorHexCode.GRAY))
		return self.graph_bar_stacked(bars, bar_colors, yticklabels, xlabel=xlabel)

	def graph_bar_stacked(self, bars, bar_colors, yticklabels, xlabel=None):
		height = 0.275
		color_bg = self.get_color('bg', ColorHexCode.WHITE)
		color_fg = self.get_color('fg', ColorHexCode.BLACK)
		ax1, ax2 = self.axes  # primary axis
		bar_container = self._barh_stacked(ax1, bars, bar_colors, height)

		yticks = [float(y) + (height / 2) for y in range(len(bars))]

		# this makes the top bar shorter than the rest
		ax1.set_yticks(yticks)
		ax1.set_yticklabels(yticklabels, color=color_fg, size=self.yticklabel_config['left']['size'])

		ax2.set_yticks(yticks)
		ax2.set_yticklabels(
			[self.yticklabel_config['right']['format'].format(*subbar, PERCENT=PERCENT_FORMAT) for subbar in bars],
			color=color_fg,
			size=self.yticklabel_config['right']['size']
		)
		ax2.set_ylim(ax1.get_ylim())

		# remove the y-axis tick marks
		self._ax_hide_ticks(ax1)
		self._ax_hide_ticks(ax2)
		self._ax_set_spine_color(ax1, color_bg)
		self._ax_set_spine_color(ax2, color_bg)

		if xlabel:
			ax1.set_xlabel(xlabel, color=color_fg, size=12)
		return bar_container

class CampaignLineGraph(CampaignGraph):
	def __init__(self, *args, **kwargs):
		super(CampaignLineGraph, self).__init__(*args, **kwargs)

	def _load_graph(self, info_cache):
		raise NotImplementedError()

class CampaignPieGraph(CampaignGraph):
	def __init__(self, *args, **kwargs):
		super(CampaignPieGraph, self).__init__(*args, **kwargs)
		self.figure.subplots_adjust(top=0.85, right=0.75, bottom=0.05, left=0.05)

	def _load_graph(self, info_cache):
		raise NotImplementedError()

	def _graph_null_pie(self, title):
		ax = self.axes[0]
		ax.pie(
			(100,),
			autopct='%1.0f%%',
			colors=(self.get_color('pie_low', ColorHexCode.GRAY),),
			labels=(title,),
			shadow=True,
			startangle=225,
			textprops={'color': self.get_color('fg', ColorHexCode.BLACK)}
		)
		ax.axis('equal')
		return

	def graph_pie(self, parts, autopct=None, labels=None, legend_labels=None):
		colors = color.get_scale(
			self.get_color('pie_low', ColorHexCode.BLACK),
			self.get_color('pie_high', ColorHexCode.GRAY),
			len(parts),
			ascending=False
		)
		ax = self.axes[0]
		pie = ax.pie(
			parts,
			autopct=autopct,
			colors=colors,
			explode=[0.1] + ([0] * (len(parts) - 1)),
			labels=labels or tuple("{0:{PERCENT}}%".format(p, PERCENT=PERCENT_FORMAT) for p in parts),
			labeldistance=1.15,
			shadow=True,
			startangle=45,
			textprops={'color': self.get_color('fg', ColorHexCode.BLACK)},
			wedgeprops={'linewidth': 0}
		)
		ax.axis('equal')
		if legend_labels is not None:
			self.add_legend_patch(tuple(zip(colors, legend_labels)), fontsize='x-small')
		return pie

@export_graph_provider
class CampaignGraphDepartmentComparison(CampaignBarGraph):
	"""Display a graph which compares the different departments."""
	graph_title = 'Department Comparison'
	name_human = 'Bar - Department Comparison'
	subplot_adjustment = {'top': 0.9, 'right': 0.775, 'bottom': 0.075, 'left': 0.225}
	yticklabel_config = {
		'left': {'size': 10},
		'right': {'format': "{0:{PERCENT}}%, {1:{PERCENT}}%", 'size': 10}
	}
	def _load_graph(self, info_cache):
		messages = info_cache['messages']['edges']
		messages = [message['node'] for message in messages if message['node']['companyDepartment'] is not None]
		if not messages:
			self._graph_null_bar('')
			return
		messages = dict((message['id'], message) for message in messages)

		visits = info_cache['visits']['edges']
		visits = [visit['node'] for visit in visits if visit['node']['messageId'] in messages]
		visits = unique(visits, key=lambda visit: visit['messageId'])
		visits = dict((visit['id'], visit) for visit in visits)

		creds = info_cache['credentials']['edges']
		creds = [cred['node'] for cred in creds if cred['node']['messageId'] in messages]
		creds = unique(creds, key=lambda cred: cred['messageId'])
		creds = dict((cred['id'], cred) for cred in creds)

		department_messages = collections.Counter()
		department_messages.update(message['companyDepartment']['name'] for message in messages.values())

		department_visits = collections.Counter()
		department_visits.update(messages[visit['messageId']]['companyDepartment']['name'] for visit in visits.values())

		department_credentials = collections.Counter()
		department_credentials.update(messages[cred['messageId']]['companyDepartment']['name'] for cred in creds.values())

		bars = []
		department_names = tuple(department_messages.keys())
		for department_name in department_names:
			dep_messages = float(department_messages[department_name])
			dep_creds = float(department_credentials.get(department_name, 0)) / dep_messages * 100
			dep_visits = (float(department_visits.get(department_name, 0)) / dep_messages * 100) - dep_creds
			bars.append((
				dep_creds,
				dep_visits,
				(100.0 - (dep_creds + dep_visits))
			))
		bar_colors = (
			self.get_color('map_marker1', ColorHexCode.RED),
			self.get_color('map_marker2', ColorHexCode.YELLOW),
			self.get_color('bar_bg', ColorHexCode.GRAY)
		)
		self.graph_bar_stacked(
			bars,
			bar_colors,
			department_names
		)
		self.add_legend_patch(tuple(zip(bar_colors[:2], ('With Credentials', 'Without Credentials'))), fontsize=10)
		return

@export_graph_provider
class CampaignGraphOverview(CampaignBarGraph):
	"""Display a graph which represents an overview of the campaign."""
	graph_title = 'Campaign Overview'
	name_human = 'Bar - Campaign Overview'
	def _load_graph(self, info_cache):
		visits = info_cache['visits']['edges']
		creds = info_cache['credentials']['edges']
		messages = info_cache['messages']
		messages_count = messages['total']
		messages_opened = [message['node'] for message in messages['edges'] if message['node']['opened'] is not None]

		bars = []
		bars.append(messages_count)
		bars.append(len(messages_opened))
		bars.append(len(visits))
		bars.append(len(unique(visits, key=lambda visit: visit['node']['messageId'])))
		if len(creds):
			bars.append(len(creds))
			bars.append(len(unique(creds, key=lambda cred: cred['node']['messageId'])))
		yticklabels = ('Messages', 'Opened', 'Visits', 'Unique\nVisits', 'Credentials', 'Unique\nCredentials')
		self.graph_bar(bars, yticklabels[:len(bars)])
		return

@export_graph_provider
class CampaignGraphVisitorInfo(CampaignBarGraph):
	"""Display a graph which shows the different operating systems seen from visitors."""
	graph_title = 'Campaign Visitor OS Information'
	name_human = 'Bar - Visitor OS Information'
	def _load_graph(self, info_cache):
		visits = info_cache['visits']['edges']
		if not len(visits):
			self._graph_null_bar('No Visitor Information')
			return
		operating_systems = collections.Counter()
		for visit in visits:
			user_agent = None
			if visit['node']['userAgent']:
				user_agent = ua_parser.parse_user_agent(visit['node']['userAgent'])
			operating_systems.update([user_agent.os_name if user_agent and user_agent.os_name else 'Unknown OS'])
		os_names = sorted(operating_systems.keys())
		bars = [operating_systems[os_name] for os_name in os_names]
		self.graph_bar(bars, os_names)
		return

@export_graph_provider
class CampaignGraphVisitorInfoPie(CampaignPieGraph):
	"""Display a graph which compares the different operating systems seen from visitors."""
	graph_title = 'Campaign Visitor OS Information'
	name_human = 'Pie - Visitor OS Information'
	def _load_graph(self, info_cache):
		visits = info_cache['visits']['edges']
		if not len(visits):
			self._graph_null_pie('No Visitor Information')
			return

		operating_systems = collections.Counter()
		for visit in visits:
			ua = ua_parser.parse_user_agent(visit['node']['userAgent'])
			operating_systems.update([ua.os_name or 'Unknown OS' if ua else 'Unknown OS'])
		(os_names, count) = tuple(zip(*reversed(sorted(operating_systems.items(), key=lambda item: item[1]))))
		self.graph_pie(count, labels=tuple("{0:,}".format(os) for os in count), legend_labels=os_names)
		return

@export_graph_provider
class CampaignGraphVisitsTimeline(CampaignLineGraph):
	"""Display a graph which represents the visits of a campaign over time."""
	graph_title = 'Campaign Visits Timeline'
	name_human = 'Line - Visits Timeline'
	def _load_graph(self, info_cache):
		# define the necessary colors
		color_bg = self.get_color('bg', ColorHexCode.WHITE)
		color_fg = self.get_color('fg', ColorHexCode.BLACK)
		color_line_bg = self.get_color('line_bg', ColorHexCode.WHITE)
		color_line_fg = self.get_color('line_fg', ColorHexCode.BLACK)
		visits = info_cache['visits']['edges']
		first_seen_timestamps = [utilities.datetime_utc_to_local(visit['node']['firstSeen']) for visit in visits]

		ax = self.axes[0]
		ax.tick_params(
			axis='both',
			which='both',
			colors=color_fg,
			top=False,
			bottom=False
		)
		ax.set_facecolor(color_line_bg)
		ax.set_ylabel('Number of Visits', color=self.get_color('fg', ColorHexCode.WHITE), size=10)
		self._ax_hide_ticks(ax)
		self._ax_set_spine_color(ax, color_bg)
		if not len(first_seen_timestamps):
			ax.set_yticks((0,))
			ax.set_xticks((0,))
			return

		first_seen_timestamps.sort()
		ax.plot_date(
			first_seen_timestamps,
			range(1, len(first_seen_timestamps) + 1),
			'-',
			color=color_line_fg,
			linewidth=6
		)
		self.figure.autofmt_xdate()
		self.figure.subplots_adjust(top=0.85, right=0.95, bottom=0.25, left=0.1)

		locator = dates.AutoDateLocator()
		ax.xaxis.set_major_locator(locator)
		ax.xaxis.set_major_formatter(dates.AutoDateFormatter(locator))
		return

@export_graph_provider
class CampaignGraphMessageResults(CampaignPieGraph):
	"""Display the percentage of messages which resulted in a visit."""
	graph_title = 'Campaign Message Results'
	name_human = 'Pie - Message Results'
	def _load_graph(self, info_cache):
		messages = info_cache['messages']
		messages_count = messages['total']
		if not messages_count:
			self._graph_null_pie('No Messages Sent')
			return
		visits_count = len(unique(info_cache['visits']['edges'], key=lambda visit: visit['node']['messageId']))
		credentials_count = len(unique(info_cache['credentials']['edges'], key=lambda cred: cred['node']['messageId']))

		if not credentials_count <= visits_count <= messages_count:
			raise ValueError('credential visit and message counts are inconsistent')
		labels = ['Without Visit', 'With Visit', 'With Credentials']
		sizes = []
		sizes.append((float(messages_count - visits_count) / float(messages_count)) * 100)
		sizes.append((float(visits_count - credentials_count) / float(messages_count)) * 100)
		sizes.append((float(credentials_count) / float(messages_count)) * 100)
		if not credentials_count:
			labels.pop()
			sizes.pop()
		if not visits_count:
			labels.pop()
			sizes.pop()
		self.graph_pie(sizes, legend_labels=labels)
		return

class CampaignGraphVisitsMap(CampaignGraph):
	"""A base class to display a map which shows the locations of visit origins."""
	graph_title = 'Campaign Visit Locations'
	is_available = has_matplotlib_basemap
	draw_states = False
	def _load_graph(self, info_cache):
		visits = unique(info_cache['visits']['edges'], key=lambda visit: visit['node']['messageId'])
		visits = [visit['node'] for visit in visits]
		cred_ips = set(cred['node']['messageId'] for cred in info_cache['credentials']['edges'])
		cred_ips = set([visit['ip'] for visit in visits if visit['messageId'] in cred_ips])

		color_fg = self.get_color('fg', ColorHexCode.BLACK)
		color_land = self.get_color('map_land', ColorHexCode.GRAY)
		color_water = self.get_color('map_water', ColorHexCode.WHITE)

		ax = self.axes[0]
		bm = mpl_toolkits.basemap.Basemap(resolution='c', ax=ax, **self.basemap_args)
		if self.draw_states:
			bm.drawstates()
		bm.drawcoastlines()
		bm.drawcountries()
		bm.fillcontinents(color=color_land, lake_color=color_water)
		parallels = bm.drawparallels(
			(-60, -30, 0, 30, 60),
			labels=(1, 1, 0, 0)
		)
		self._map_set_line_color(parallels, color_fg)

		meridians = bm.drawmeridians(
			(0, 90, 180, 270),
			labels=(0, 0, 0, 1)
		)
		self._map_set_line_color(meridians, color_fg)
		bm.drawmapboundary(
			fill_color=color_water,
			linewidth=0
		)
		if not visits:
			return

		base_markersize = self.markersize_scale
		base_markersize = max(base_markersize, 3.05)
		base_markersize = min(base_markersize, 9)
		self._plot_visitor_map_points(bm, visits, cred_ips, base_markersize)
		self.add_legend_patch(((self.color_with_creds, 'With Credentials'), (self.color_without_creds, 'Without Credentials')))
		return

	def _plot_visitor_map_points(self, bm, visits, cred_ips, base_markersize):
		ctr = collections.Counter()
		ctr.update([visit['ip'] for visit in visits])
		geo_locations = {}
		for visit in visits:
			if not visit['ipGeoloc']:
				continue
			ip_address = visit['ip']
			geo_locations[ip_address] = geoip.GeoLocation.from_graphql(ip_address, visit['ipGeoloc'])

		o_high = float(max(ctr.values())) if ctr else 0.0
		o_low = float(min(ctr.values())) if ctr else 0.0
		color_with_creds = self.color_with_creds
		color_without_creds = self.color_without_creds
		for visitor_ip, geo_location in geo_locations.items():
			if not (geo_location.coordinates.longitude and geo_location.coordinates.latitude):
				continue
			occurrences = ctr[visitor_ip]
			pts = bm(geo_location.coordinates.longitude, geo_location.coordinates.latitude)
			if o_high == o_low:
				markersize = 2.0
			else:
				markersize = 1.0 + (float(occurrences) - o_low) / (o_high - o_low)
			markersize = markersize * base_markersize
			bm.plot(
				pts[0],
				pts[1],
				'o',
				markeredgewidth=0,
				markerfacecolor=(color_with_creds if visitor_ip in cred_ips else color_without_creds),
				markersize=markersize
			)
		return

	def _map_set_line_color(self, map_lines, line_color):
		for sub_lines, texts in map_lines.values():
			for line in sub_lines:
				line.set_color(line_color)
			for text in texts:
				text.set_color(line_color)

	@property
	def color_with_creds(self):
		return self.get_color('map_marker1', ColorHexCode.RED)

	@property
	def color_without_creds(self):
		return self.get_color('map_marker2', ColorHexCode.YELLOW)

@export_graph_provider
class CampaignGraphVisitsMapUSA(CampaignGraphVisitsMap):
	"""Display a map of the USA which shows the locations of visit origins."""
	name_human = 'Map - Visit Locations (USA)'
	draw_states = True
	basemap_args = dict(projection='lcc', lat_1=30, lon_0=-90, llcrnrlon=-122.5, llcrnrlat=12.5, urcrnrlon=-45, urcrnrlat=50)

@export_graph_provider
class CampaignGraphVisitsMapWorld(CampaignGraphVisitsMap):
	"""Display a map of the world which shows the locations of visit origins."""
	name_human = 'Map - Visit Locations (World)'
	basemap_args = dict(projection='kav7', lon_0=0)

@export_graph_provider
class CampaignGraphPasswordComplexityPie(CampaignPieGraph):
	"""Display a graph which displays the number of passwords which meet standard complexity requirements."""
	graph_title = 'Campaign Password Complexity'
	name_human = 'Pie - Password Complexity'
	def _load_graph(self, info_cache):
		passwords = set(cred['node']['password'] for cred in info_cache['credentials']['edges'])
		if not len(passwords):
			self._graph_null_pie('No Credential Information')
			return
		ctr = collections.Counter()
		ctr.update(self._check_complexity(password) for password in passwords)
		self.graph_pie((ctr[True], ctr[False]), autopct='%1.1f%%', legend_labels=('Complex', 'Not Complex'))
		return

	def _check_complexity(self, password):
		if len(password) < 8:
			return False
		met = 0
		for char_set in (string.ascii_uppercase, string.ascii_lowercase, string.digits, string.punctuation):
			for char in password:
				if char in char_set:
					met += 1
					break
		return met >= 3

class CampaignGraphComparison(GraphBase):
	"""Display selected campaigns data by order of campaign start date."""
	graph_title = 'Campaign Comparison Graph'
	name_human = 'Graph'
	def __init__(self, *args, **kwargs):
		super(CampaignGraphComparison, self).__init__(*args, **kwargs)
		ax = self.axes[0]
		self.axes.append(ax.twinx())
		ax2 = self.axes[1]
		self._config_axes(ax, ax2)
		self._campaigns = []

	def _calc(self, stats, key, comp_key='messages'):
		return 0 if stats[comp_key] == 0 else (float(stats[key]) / stats[comp_key]) * 100

	def _config_axes(self, ax, ax2):
		# define the necessary colors
		color_bg = self.get_color('bg', ColorHexCode.WHITE)
		color_fg = self.get_color('fg', ColorHexCode.BLACK)
		color_line_bg = self.get_color('line_bg', ColorHexCode.WHITE)
		ax.tick_params(
			axis='both',
			which='both',
			colors=color_fg,
			top=False,
			bottom=False
		)
		ax2.tick_params(
			axis='both',
			which='both',
			colors=color_fg,
			top=False,
			bottom=False
		)
		ax.set_facecolor(color_line_bg)
		ax2.set_facecolor(color_line_bg)
		title = pyplot.title('Campaign Comparison', color=color_fg, size=self.markersize_scale * 1.75, loc='left')
		title.set_position([0.075, 1.05])
		ax.set_ylabel('Percent Visits/Credentials', color=color_fg, size=self.markersize_scale * 1.5)
		ax.set_xlabel('Campaign Name', color=color_fg, size=self.markersize_scale * 1.5)
		self._ax_hide_ticks(ax)
		self._ax_hide_ticks(ax2)
		ax2.set_ylabel('Messages', color=color_fg, size=self.markersize_scale * 1.25, rotation=270, labelpad=20)
		self._ax_set_spine_color(ax, color_bg)
		self._ax_set_spine_color(ax2, color_bg)
		ax2.get_yaxis().set_major_locator(ticker.MaxNLocator(integer=True))
		ax.tick_params(axis='x', labelsize=10, pad=5)

	def load_graph(self, campaigns):
		"""
		Load the information to compare the specified and paint it to the
		canvas. Campaigns are graphed on the X-axis in the order that they are
		provided. No sorting of campaigns is done by this method.

		:param tuple campaigns: A tuple containing campaign IDs to compare.
		"""
		ax = self.axes[0]
		ax2 = self.axes[1]
		ax.clear()
		ax2.clear()
		self._config_axes(ax, ax2)

		rpc = self.rpc
		ellipsize = lambda text: (text if len(text) < 20 else text[:17] + '...')
		visits_line_color = self.get_color('line_fg', ColorHexCode.RED)
		creds_line_color = self.get_color('map_marker1', ColorHexCode.BLACK)
		messages_color = '#046D8B'
		trained_color = '#77c67f'

		ax.grid(True)
		ax.set_xticks(range(len(campaigns)))
		ax.set_xticklabels([ellipsize(self._get_graphql_campaign_name(cid)) for cid in campaigns])
		for tick in ax.xaxis.get_major_ticks():
			tick.label.set_fontsize(self.markersize_scale * 1.25)
		labels = ax.get_xticklabels()
		pyplot.setp(labels, rotation=15)
		self._campaigns = campaigns

		campaigns = [rpc('/campaign/stats', cid) for cid in campaigns]
		ax2.plot([stats['messages'] for stats in campaigns], label='Messages', color=messages_color, lw=3)
		if sum(stats['messages-trained'] for stats in campaigns):
			ax.plot([self._calc(stats, 'messages-trained', 'visits-unique') for stats in campaigns], label='Trained (Visited)', color=trained_color, lw=3)
			ax.plot([self._calc(stats, 'messages-trained') for stats in campaigns], label='Trained (All)', color=trained_color, lw=3, ls='dashed')
		ax.plot([self._calc(stats, 'visits') for stats in campaigns], label='Visits', color=visits_line_color, lw=3)
		ax.plot([self._calc(stats, 'visits-unique') for stats in campaigns], label='Unique Visits', color=visits_line_color, lw=3, ls='dashed')
		if sum(stats['credentials'] for stats in campaigns):
			ax.plot([self._calc(stats, 'credentials') for stats in campaigns], label='Credentials', color=creds_line_color, lw=3)
			ax.plot([self._calc(stats, 'credentials-unique') for stats in campaigns], label='Unique Credentials', color=creds_line_color, lw=3, ls='dashed')
		ax.set_ylim((0, 100))
		ax2.set_ylim(bottom=0)
		self.canvas.set_size_request(500 + 50 * (len(campaigns) - 1), 500)

		legend_patch = [
			(visits_line_color, 'solid', 'Visits'),
			(visits_line_color, 'dotted', 'Unique Visits')
		]
		if sum(stats['credentials'] for stats in campaigns):
			legend_patch.extend([
				(creds_line_color, 'solid', 'Credentials'),
				(creds_line_color, 'dotted', 'Unique Credentials')
			])
		if sum(stats['messages-trained'] for stats in campaigns):
			legend_patch.extend([
				(trained_color, 'solid', 'Trained (Visited)'),
				(trained_color, 'dotted', 'Trained (All)')
			])
		legend_patch.append(
			(messages_color, 'solid', 'Messages')
		)
		self.add_legend_patch(legend_patch)
		pyplot.tight_layout()

	def _get_graphql_campaign_name(self, campaign_id=None):
		results = self.rpc.graphql("""\
		query getCampaignName($id: String!) {
			db {
				campaign(id: $id) {
					name
				}
			}
		}""", {'id': campaign_id or self.config['campaign_id']})
		return results['db']['campaign']['name']

	def add_legend_patch(self, legend_rows, fontsize=None):
		if matplotlib.__version__ == '3.0.2':
			self.logger.warning('skipping legend patch with matplotlib v3.0.2 for compatibility')
			return
		if self._legend is not None:
			self._legend.remove()
			self._legend = None
		legend_bbox = self.figure.legend(
			tuple(lines.Line2D([], [], color=patch_color, lw=3, ls=style) for patch_color, style, _ in legend_rows),
			tuple(label for _, _, label in legend_rows),
			borderaxespad=1,
			columnspacing=1.5,
			fontsize=self.fontsize_scale,
			ncol=3,
			frameon=True,
			handlelength=2,
			handletextpad=0.5,
			labelspacing=0.5,
			loc='upper right'
		)
		legend_bbox.get_frame().set_facecolor(self.get_color('line_bg', ColorHexCode.GRAY))
		for text in legend_bbox.get_texts():
			text.set_color('white')
		legend_bbox.legendPatch.set_linewidth(0)
		self._legend = legend_bbox

	def refresh(self):
		self.load_graph(self._campaigns)
