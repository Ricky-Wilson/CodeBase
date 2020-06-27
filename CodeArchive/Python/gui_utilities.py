#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  king_phisher/client/gui_utilities.py
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

import calendar
import contextlib
import copy
import datetime
import functools
import logging
import os
import socket
import threading
import xml.sax.saxutils as saxutils

from king_phisher import find
from king_phisher import utilities

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource

GObject.type_register(GtkSource.View)

GOBJECT_PROPERTY_MAP = {
	'calendar': None,  # delayed definition
	'checkbutton': 'active',
	'combobox': (
		lambda c, v: c.set_active_iter(gtk_list_store_search(c.get_model(), v)),
		lambda c: c.get_model().get_value(c.get_active_iter() or c.get_model().get_iter_first(), 0)
	),
	'entry': 'text',
	'spinbutton': 'value',
	'switch': 'active',
	'textview': (
		lambda t, v: t.get_buffer().set_text(v),
		lambda t: t.get_buffer().get_text(t.get_buffer().get_start_iter(), t.get_buffer().get_end_iter(), False)
	)
}
"""
The dictionary which maps GObjects to either the names of properties to
store text or a tuple which contains a set and get function. If a tuple
of two functions is specified the set function will be provided two
parameters, the object and the value and the get function will just be
provided the object.
"""

# modified from the official python3 work-around per
# https://docs.python.org/3.0/whatsnew/3.0.html#ordering-comparisons
def _cmp(item1, item2):
	"""
	Compare two arbitrary Python objects. The object types should either be the
	same or one or both may be ``None``.

	:rtype: int
	:return: ``-1`` if *item1* is less than *item2*, ``0`` if they are equal or
		``1`` if *item1* is greater than *item2*.
	"""
	if item1 is None:
		return 0 if item2 is None else -1
	if item2 is None:
		return 1
	return (item1 > item2) - (item1 < item2)

def which_glade():
	"""
	Locate the glade data file which stores the UI information in a Gtk Builder
	format.

	:return: The path to the glade data file.
	:rtype: str
	"""
	return find.data_file(os.environ.get('KING_PHISHER_GLADE_FILE', 'king-phisher-client.ui'))

def _store_extend(store, things, clear=False):
	if clear:
		store.clear()
	for thing in things:
		store.append(thing)

def delayed_signal(delay=500):
	"""
	A decorator to delay the execution of a signal handler to aggregate emission
	into a single event. This can for example be used to run a handler when a
	:py:class:`Gtk.Entry` widget's ``changed`` signal is emitted but not after
	every single key press meaning the handler can perform network operations to
	validate or otherwise process input.

	.. note::
		The decorated function **must** be a method. The wrapper installed by
		this decorator will automatically add an attribute to the class to track
		invoked instances to ensure the timeout is respected.

	.. versionadded:: 1.14.0

	:param int delay: The delay in milliseconds from the original emission
		before the handler should be executed.
	"""
	def decorator(function):
		src_name = '__delayed_source_' + function.__name__
		@functools.wraps(function)
		def wrapped(self, *args, **kwargs):
			def new_function(self, *args, **kwargs):
				setattr(self, src_name, None)
				return function(self, *args, **kwargs)
			src = getattr(self, src_name, None)
			if src is not None:
				return
			src = GLib.timeout_add(delay, new_function, self, *args, **kwargs)
			setattr(self, src_name, src)
		return wrapped
	return decorator

def glib_idle_add_store_extend(store, things, clear=False, wait=False):
	"""
	Extend a GTK store object (either :py:class:`Gtk.ListStore` or
	:py:class:`Gtk.TreeStore`) object using :py:func:`GLib.idle_add`. This
	function is suitable for use in non-main GUI threads for synchronizing data.

	:param store: The GTK storage object to add *things* to.
	:type store: :py:class:`Gtk.ListStore`, :py:class:`Gtk.TreeStore`
	:param tuple things: The array of things to add to *store*.
	:param bool clear: Whether or not to clear the storage object before adding *things* to it.
	:param bool wait: Whether or not to wait for the operation to complete before returning.
	:return: Regardless of the *wait* parameter, ``None`` is returned.
	:rtype: None
	"""
	if not isinstance(store, Gtk.ListStore):
		raise TypeError('store must be a Gtk.ListStore instance')
	idle_add = glib_idle_add_wait if wait else glib_idle_add_once
	idle_add(_store_extend, store, things, clear)

def glib_idle_add_once(function, *args, **kwargs):
	"""
	Execute *function* in the main GTK loop using :py:func:`GLib.idle_add`
	one time. This is useful for threads that need to update GUI data.

	:param function function: The function to call.
	:param args: The positional arguments to *function*.
	:param kwargs: The key word arguments to *function*.
	:return: The result of the function call.
	"""
	@functools.wraps(function)
	def wrapper():
		function(*args, **kwargs)
		return False
	return GLib.idle_add(wrapper)

def glib_idle_add_wait(function, *args, **kwargs):
	"""
	Execute *function* in the main GTK loop using :py:func:`GLib.idle_add`
	and block until it has completed. This is useful for threads that need
	to update GUI data.

	:param function function: The function to call.
	:param args: The positional arguments to *function*.
	:param kwargs: The key word arguments to *function*.
	:return: The result of the function call.
	"""
	gsource_completed = threading.Event()
	results = []

	@functools.wraps(function)
	def wrapper():
		results.append(function(*args, **kwargs))
		gsource_completed.set()
		return False
	GLib.idle_add(wrapper)
	gsource_completed.wait()
	return results.pop()

def gobject_get_value(gobject, gtype=None):
	"""
	Retrieve the value of a GObject widget. Only objects with corresponding
	entries present in the :py:data:`.GOBJECT_PROPERTY_MAP` can be processed by
	this function.

	:param gobject: The object to retrieve the value for.
	:type gobject: :py:class:`GObject.Object`
	:param str gtype: An explicit type to treat *gobject* as.
	:return: The value of *gobject*.
	:rtype: str
	"""
	gtype = (gtype or gobject.__class__.__name__)
	gtype = gtype.lower()
	if isinstance(GOBJECT_PROPERTY_MAP[gtype], (list, tuple)):
		try:
			value = GOBJECT_PROPERTY_MAP[gtype][1](gobject)
		except AttributeError:
			return None
	else:
		value = gobject.get_property(GOBJECT_PROPERTY_MAP[gtype])
	return value

def gobject_set_value(gobject, value, gtype=None):
	"""
	Set the value of a GObject widget. Only objects with corresponding entries
	present in the :py:data:`.GOBJECT_PROPERTY_MAP` can be processed by this
	function.

	:param gobject: The object to set the value for.
	:type gobject: :py:class:`GObject.Object`
	:param value: The value to set for the object.
	:param str gtype: An explicit type to treat *gobject* as.
	"""
	gtype = (gtype or gobject.__class__.__name__)
	gtype = gtype.lower()
	if gtype not in GOBJECT_PROPERTY_MAP:
		raise ValueError('unsupported gtype: ' + gtype)
	if isinstance(GOBJECT_PROPERTY_MAP[gtype], (list, tuple)):
		GOBJECT_PROPERTY_MAP[gtype][0](gobject, value)
	else:
		gobject.set_property(GOBJECT_PROPERTY_MAP[gtype], value)

@contextlib.contextmanager
def gobject_signal_blocked(gobject, signal_name):
	"""
	This is a context manager that can be used with the 'with' statement
	to execute a block of code while *signal_name* is blocked.

	:param gobject: The object to block the signal on.
	:type gobject: :py:class:`GObject.Object`
	:param str signal_name: The name of the signal to block.
	"""
	signal_id = GObject.signal_lookup(signal_name, gobject.__class__)
	handler_id = GObject.signal_handler_find(gobject, GObject.SignalMatchType.ID, signal_id, 0, None, 0, 0)
	GObject.signal_handler_block(gobject, handler_id)
	yield
	GObject.signal_handler_unblock(gobject, handler_id)

def gobject_signal_accumulator(test=None):
	"""
	Create an accumulator function for use with GObject signals. All return
	values will be collected and returned in a list. If provided, *test* is a
	callback that will be called with two arguments, the return value from the
	handler and the list of accumulated return values.

	.. code-block:: python

	  stop = test(retval, accumulated)

	:param test: A callback to test whether additional handler should be executed.
	"""
	if test is None:
		test = lambda retval, accumulated: True

	def _accumulator(_, accumulated, retval):
		if accumulated is None:
			accumulated = []
		stop = test(retval, accumulated)
		accumulated.append(retval)
		return (stop, accumulated)
	return _accumulator

def gtk_calendar_get_pydate(gtk_calendar):
	"""
	Get the Python date from a :py:class:`Gtk.Calendar` instance. If the day
	in *gtk_calendar* is not within the valid range for the specified month, it
	will be rounded to the closest value (i.e. 0 for unset will become 1 etc.).

	:param gtk_calendar: The calendar to get the date from.
	:type gtk_calendar: :py:class:`Gtk.Calendar`
	:return: The date as returned by the calendar's :py:meth:`~Gtk.Calendar.get_date` method.
	:rtype: :py:class:`datetime.date`
	"""
	if not isinstance(gtk_calendar, Gtk.Calendar):
		raise ValueError('calendar must be a Gtk.Calendar instance')
	year, month, day = gtk_calendar.get_date()
	month += 1  # account for Gtk.Calendar starting at 0
	_, last_day_of_month = calendar.monthrange(year, month)
	day = max(1, min(day, last_day_of_month))
	return datetime.date(year, month, day)

def gtk_calendar_set_pydate(gtk_calendar, pydate):
	"""
	Set the date on a :py:class:`Gtk.Calendar` instance from a Python
	:py:class:`datetime.date` object.

	:param gtk_calendar: The gtk_calendar to set the date for.
	:type gtk_calendar: :py:class:`Gtk.Calendar`
	:param pydate: The date to set on the gtk_calendar.
	:type pydate: :py:class:`datetime.date`
	"""
	gtk_calendar.select_month(pydate.month - 1, pydate.year)
	gtk_calendar.select_day(pydate.day)

GOBJECT_PROPERTY_MAP['calendar'] = (
	gtk_calendar_set_pydate,
	gtk_calendar_get_pydate
)

def gtk_combobox_get_active_cell(combobox, column=None):
	"""
	Get the active value from a GTK combobox and it's respective model. If
	nothing is selected, ``None`` is returned.

	.. versionadded:: 1.14.0

	:param combobox: The combobox to retrieve the active model value for.
	:param int column: The column ID to retrieve from the selected row. If not
		specified, the combobox's ``id-column`` property will be used.
	:return: The selected model row's value.
	"""
	row = gtk_combobox_get_active_row(combobox)
	if row is None:
		return None
	if column is None:
		column = combobox.get_property('id-column')
	return row[column]

def gtk_combobox_get_active_row(combobox):
	"""
	Get the active row from a GTK combobox and it's respective model. If
	nothing is selected, ``None`` is returned.

	.. versionadded:: 1.14.0

	:param combobox: The combobox to retrieve the active model row for.
	:return: The selected model row.
	"""
	active = combobox.get_active()
	if active == -1:
		return None
	model = combobox.get_model()
	return model[active]

def gtk_combobox_get_entry_text(combobox):
	"""
	Get the text from a combobox's entry widget.

	.. versionadded:: 1.14.0

	:param combobox: The combobox to retrieve the entry text for.
	:return: The value of the entry text.
	:rtype: str
	"""
	if not combobox.get_has_entry():
		raise ValueError('the specified combobox does not have an entry')
	entry = combobox.get_child()
	return entry.get_text()

def gtk_combobox_set_entry_completion(combobox):
	"""
	Add completion for a :py:class:`Gtk.ComboBox` widget which contains an
	entry. They combobox's ``entry-text-column`` property it used to determine
	which column in its model contains the strings to suggest for completion.

	.. versionadded:: 1.14.0

	:param combobox: The combobox to add completion for.
	:type: :py:class:`Gtk.ComboBox`
	"""
	utilities.assert_arg_type(combobox, Gtk.ComboBox)
	completion = Gtk.EntryCompletion()
	completion.set_model(combobox.get_model())
	completion.set_text_column(combobox.get_entry_text_column())
	entry = combobox.get_child()
	entry.set_completion(completion)

def gtk_list_store_search(list_store, value, column=0):
	"""
	Search a :py:class:`Gtk.ListStore` for a value and return a
	:py:class:`Gtk.TreeIter` to the first match.

	:param list_store: The list store to search.
	:type list_store: :py:class:`Gtk.ListStore`
	:param value: The value to search for.
	:param int column: The column in the row to check.
	:return: The row on which the value was found.
	:rtype: :py:class:`Gtk.TreeIter`
	"""
	for row in list_store:
		if row[column] == value:
			return row.iter
	return None

def gtk_listbox_populate_labels(listbox, label_strings):
	"""
	Formats and adds labels to a listbox. Each label is styled and added as a
	separate entry.

	.. versionadded:: 1.13.0

	:param listbox: Gtk Listbox to put the labels in.
	:type listbox: :py:class:`Gtk.listbox`
	:param list label_strings: List of strings to add to the Gtk Listbox as labels.
	"""
	gtk_widget_destroy_children(listbox)
	for label_text in label_strings:
		label = Gtk.Label()
		label.set_markup("<span font=\"smaller\"><tt>{0}</tt></span>".format(saxutils.escape(label_text)))
		label.set_property('halign', Gtk.Align.START)
		label.set_property('use-markup', True)
		label.set_property('valign', Gtk.Align.START)
		label.set_property('visible', True)
		listbox.add(label)

def gtk_listbox_populate_urls(listbox, url_strings, signals=None):
	"""
	Format and adds URLs to a list box. Each URL is styeled and added as a
	seperate entry.

	.. versionadded:: 1.14.0

	:param listbox: Gtk Listbox to put the labels in.
	:type listbox: :py:class:`Gtk.listbox`
	:param list url_strings: List of URL strings to add to the Gtk Listbox as labels.
	:param dict signals: A dictionary, keyed by signal names to signal handler
		functions for the labels added to the listbox.
	"""
	gtk_widget_destroy_children(listbox)
	signals = signals or {}
	for url in url_strings:
		label = Gtk.Label()
		for signal, handler in signals.items():
			label.connect(signal, handler)
		label.set_markup("<a href=\"{0}\">{1}</a>".format(url.replace('"', '&quot;'), saxutils.escape(url)))
		label.set_property('halign', Gtk.Align.START)
		label.set_property('track-visited-links', False)
		label.set_property('use-markup', True)
		label.set_property('valign', Gtk.Align.START)
		label.set_property('visible', True)
		listbox.add(label)

def gtk_menu_get_item_by_label(menu, label):
	"""
	Retrieve a menu item from a menu by it's label. If more than one items share
	the same label, only the first is returned.

	:param menu: The menu to search for the item in.
	:type menu: :py:class:`Gtk.Menu`
	:param str label: The label to search for in *menu*.
	:return: The identified menu item if it could be found, otherwise None is returned.
	:rtype: :py:class:`Gtk.MenuItem`
	"""
	for item in menu:
		if item.get_label() == label:
			return item

def gtk_menu_insert_by_path(menu, menu_path, menu_item):
	"""
	Add a new menu item into the existing menu at the path specified in
	*menu_path*.

	:param menu: The existing menu to add the new item to.
	:type menu: :py:class:`Gtk.Menu` :py:class:`Gtk.MenuBar`
	:param list menu_path: The labels of submenus to traverse to insert the new item.
	:param menu_item: The new menu item to insert.
	:type menu_item: :py:class:`Gtk.MenuItem`
	"""
	utilities.assert_arg_type(menu, (Gtk.Menu, Gtk.MenuBar), 1)
	utilities.assert_arg_type(menu_path, list, 2)
	utilities.assert_arg_type(menu_item, Gtk.MenuItem, 3)
	while len(menu_path):
		label = menu_path.pop(0)
		menu_cursor = gtk_menu_get_item_by_label(menu, label)
		if menu_cursor is None:
			raise ValueError('missing node labeled: ' + label)
		menu = menu_cursor.get_submenu()
	menu.append(menu_item)

def gtk_menu_position(event, *args):
	"""
	Create a menu at the given location for an event. This function is meant to
	be used as the *func* parameter for the :py:meth:`Gtk.Menu.popup` method.
	The *event* object must be passed in as the first parameter, which can be
	accomplished using :py:func:`functools.partial`.

	:param event: The event to retrieve the coordinates for.
	"""
	if not hasattr(event, 'get_root_coords'):
		raise TypeError('event object has no get_root_coords method')
	coords = event.get_root_coords()
	return (coords[0], coords[1], True)

def gtk_style_context_get_color(sc, color_name, default=None):
	"""
	Look up a color by it's name in the :py:class:`Gtk.StyleContext` specified
	in *sc*, and return it as an :py:class:`Gdk.RGBA` instance if the color is
	defined. If the color is not found, *default* will be returned.

	:param sc: The style context to use.
	:type sc: :py:class:`Gtk.StyleContext`
	:param str color_name: The name of the color to lookup.
	:param default: The default color to return if the specified color was not found.
	:type default: str, :py:class:`Gdk.RGBA`
	:return: The color as an RGBA instance.
	:rtype: :py:class:`Gdk.RGBA`
	"""
	found, color_rgba = sc.lookup_color(color_name)
	if found:
		return color_rgba
	if isinstance(default, str):
		color_rgba = Gdk.RGBA()
		color_rgba.parse(default)
		return color_rgba
	elif isinstance(default, Gdk.RGBA):
		return default
	return

def gtk_sync():
	"""Wait while all pending GTK events are processed."""
	while Gtk.events_pending():
		Gtk.main_iteration()

def gtk_treesortable_sort_func(model, iter1, iter2, column_id):
	column_id = column_id or 0
	item1 = model.get_value(iter1, column_id)
	item2 = model.get_value(iter2, column_id)
	return _cmp(item1, item2)

def gtk_treesortable_sort_func_numeric(model, iter1, iter2, column_id):
	"""
	Sort the model by comparing text numeric values with place holders such as
	1,337. This is meant to be set as a sorting function using
	:py:meth:`Gtk.TreeSortable.set_sort_func`. The user_data parameter must be
	the column id which contains the numeric values to be sorted.

	:param model: The model that is being sorted.
	:type model: :py:class:`Gtk.TreeSortable`
	:param iter1: The iterator of the first item to compare.
	:type iter1: :py:class:`Gtk.TreeIter`
	:param iter2: The iterator of the second item to compare.
	:type iter2: :py:class:`Gtk.TreeIter`
	:param column_id: The ID of the column containing numeric values.
	:return: An integer, -1 if item1 should come before item2, 0 if they are the same and 1 if item1 should come after item2.
	:rtype: int
	"""
	column_id = column_id or 0
	item1 = model.get_value(iter1, column_id).replace(',', '')
	item2 = model.get_value(iter2, column_id).replace(',', '')
	if item1.isdigit() and item2.isdigit():
		return _cmp(int(item1), int(item2))
	if item1.isdigit():
		return -1
	elif item2.isdigit():
		return 1
	item1 = model.get_value(iter1, column_id)
	item2 = model.get_value(iter2, column_id)
	return _cmp(item1, item2)

def gtk_treeview_selection_iterate(treeview):
	"""
	Iterate over the a treeview's selected rows.

	:param treeview: The treeview for which to iterate over.
	:type treeview: :py:class:`Gtk.TreeView`
	:return: The rows which are selected within the treeview.
	:rtype: :py:class:`Gtk.TreeIter`
	"""
	selection = treeview.get_selection()
	(model, tree_paths) = selection.get_selected_rows()
	if not tree_paths:
		return
	for tree_path in tree_paths:
		yield model.get_iter(tree_path)

def gtk_treeview_selection_to_clipboard(treeview, columns=0):
	"""
	Copy the currently selected values from the specified columns in the
	treeview to the users clipboard. If no value is selected in the treeview,
	then the clipboard is left unmodified. If multiple values are selected, they
	will all be placed in the clipboard on separate lines.

	:param treeview: The treeview instance to get the selection from.
	:type treeview: :py:class:`Gtk.TreeView`
	:param column: The column numbers to retrieve the value for.
	:type column: int, list, tuple
	"""
	treeview_selection = treeview.get_selection()
	(model, tree_paths) = treeview_selection.get_selected_rows()
	if not tree_paths:
		return
	if isinstance(columns, int):
		columns = (columns,)
	tree_iters = map(model.get_iter, tree_paths)
	selection_lines = []
	for ti in tree_iters:
		values = (model.get_value(ti, column) for column in columns)
		values = (('' if value is None else str(value)) for value in values)
		selection_lines.append(' '.join(values).strip())
	selection_lines = os.linesep.join(selection_lines)
	clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
	clipboard.set_text(selection_lines, -1)

def gtk_treeview_get_column_titles(treeview):
	"""
	Iterate over a GTK TreeView and return a tuple containing the id and title
	of each of it's columns.

	:param treeview: The treeview instance to retrieve columns from.
	:type treeview: :py:class:`Gtk.TreeView`
	"""
	for column_id, column in enumerate(treeview.get_columns()):
		column_name = column.get_title()
		yield (column_id, column_name)

def gtk_treeview_set_column_titles(treeview, column_titles, column_offset=0, renderers=None):
	"""
	Populate the column names of a GTK TreeView and set their sort IDs.

	:param treeview: The treeview to set column names for.
	:type treeview: :py:class:`Gtk.TreeView`
	:param list column_titles: The names of the columns.
	:param int column_offset: The offset to start setting column names at.
	:param list renderers: A list containing custom renderers to use for each column.
	:return: A dict of all the :py:class:`Gtk.TreeViewColumn` objects keyed by their column id.
	:rtype: dict
	"""
	columns = {}
	for column_id, column_title in enumerate(column_titles, column_offset):
		renderer = renderers[column_id - column_offset] if renderers else Gtk.CellRendererText()
		if isinstance(renderer, Gtk.CellRendererToggle):
			column = Gtk.TreeViewColumn(column_title, renderer, active=column_id)
		elif hasattr(renderer.props, 'python_value'):
			column = Gtk.TreeViewColumn(column_title, renderer, python_value=column_id)
		else:
			column = Gtk.TreeViewColumn(column_title, renderer, text=column_id)
		column.set_property('min-width', 25)
		column.set_property('reorderable', True)
		column.set_property('resizable', True)
		column.set_sort_column_id(column_id)
		treeview.append_column(column)
		columns[column_id] = column
	return columns

def gtk_widget_destroy_children(widget):
	"""
	Destroy all GTK child objects of *widget*.

	:param widget: The widget to destroy all the children of.
	:type widget: :py:class:`Gtk.Widget`
	"""
	for child in widget.get_children():
		child.destroy()

def show_dialog(message_type, message, parent, secondary_text=None, message_buttons=Gtk.ButtonsType.OK, use_markup=False, secondary_use_markup=False):
	"""
	Display a dialog and return the response. The response is dependent on
	the value of *message_buttons*.

	:param message_type: The GTK message type to display.
	:type message_type: :py:class:`Gtk.MessageType`
	:param str message: The text to display in the dialog.
	:param parent: The parent window that the dialog should belong to.
	:type parent: :py:class:`Gtk.Window`
	:param str secondary_text: Optional subtext for the dialog.
	:param message_buttons: The buttons to display in the dialog box.
	:type message_buttons: :py:class:`Gtk.ButtonsType`
	:param bool use_markup: Whether or not to treat the message text as markup.
	:param bool secondary_use_markup: Whether or not to treat the secondary text as markup.
	:return: The response of the dialog.
	:rtype: int
	"""
	dialog = Gtk.MessageDialog(parent, Gtk.DialogFlags.DESTROY_WITH_PARENT, message_type, message_buttons)
	dialog.set_property('text', message)
	dialog.set_property('use-markup', use_markup)
	dialog.set_property('secondary-text', secondary_text)
	dialog.set_property('secondary-use-markup', secondary_use_markup)
	if secondary_use_markup:
		signal_label_activate_link = lambda _, uri: utilities.open_uri(uri)
		for label in dialog.get_message_area().get_children():
			if not isinstance(label, Gtk.Label):
				continue
			label.connect('activate-link', signal_label_activate_link)
	dialog.show_all()
	response = dialog.run()
	dialog.destroy()
	return response

def show_dialog_error(*args, **kwargs):
	"""Display an error dialog with :py:func:`.show_dialog`."""
	return show_dialog(Gtk.MessageType.ERROR, *args, **kwargs)

def show_dialog_exc_socket_error(error, parent, title=None):
	"""
	Display an error dialog with details regarding a :py:exc:`socket.error`
	exception that has been raised.

	:param error: The exception instance that has been raised.
	:type error: :py:exc:`socket.error`
	:param parent: The parent window that the dialog should belong to.
	:type parent: :py:class:`Gtk.Window`
	:param title: The title of the error dialog that is displayed.
	"""
	title = title or 'Connection Error'
	if isinstance(error, socket.timeout):
		description = 'The connection to the server timed out.'
	elif len(error.args) > 1:
		error_number, error_message = error.args[:2]
		if error_number == 111:
			description = 'The server refused the connection.'
		else:
			description = "Socket error #{0} ({1}).".format((error_number or 'N/A'), error_message)
	return show_dialog(Gtk.MessageType.ERROR, title, parent, secondary_text=description)

def show_dialog_info(*args, **kwargs):
	"""Display an informational dialog with :py:func:`.show_dialog`."""
	return show_dialog(Gtk.MessageType.INFO, *args, **kwargs)

def show_dialog_warning(*args, **kwargs):
	"""Display an warning dialog with :py:func:`.show_dialog`."""
	return show_dialog(Gtk.MessageType.WARNING, *args, **kwargs)

def show_dialog_yes_no(*args, **kwargs):
	"""
	Display a dialog which asks a yes or no question with
	:py:func:`.show_dialog`.

	:return: True if the response is Yes.
	:rtype: bool
	"""
	kwargs['message_buttons'] = Gtk.ButtonsType.YES_NO
	return show_dialog(Gtk.MessageType.QUESTION, *args, **kwargs) == Gtk.ResponseType.YES

class GladeDependencies(object):
	"""
	A class for defining how objects should be loaded from a GTK Builder data
	file for use with :py:class:`.GladeGObject`.
	"""
	__slots__ = ('children', 'top_level', 'name')
	def __init__(self, children=None, top_level=None, name=None):
		children = children or ()
		utilities.assert_arg_type(children, tuple, 1)
		self.children = children
		"""A tuple of string names or :py:class:`.GladeProxy` instances listing the children widgets to load from the parent."""
		self.top_level = top_level
		"""A tuple of string names listing additional top level widgets to load such as images."""
		self.name = name
		"""The string of the name of the top level parent widget to load."""

	def __repr__(self):
		return "<{0} name='{1}' >".format(self.__class__.__name__, self.name)

class GladeProxyDestination(object):
	"""
	A class that is used to define how a :py:class:`.GladeProxy` object shall
	be loaded into a parent :py:class:`.GladeGObject` instance. This includes
	the information such as what container widget in the parent the proxied
	widget should be added to and what method should be used. The proxied widget
	will be added to the parent by calling
	:py:attr:`~.GladeProxyDestination.method` with the proxied widget as the
	first argument.
	"""
	__slots__ = ('widget', 'method', 'args', 'kwargs')
	def __init__(self, method, widget=None, args=None, kwargs=None):
		"""
		:param str method: The method of the container *widget* to use to add
			the proxied widget.
		:param str widget: The widget name to add the proxied widget to. If this
			value is ``None``, the proxied widget is added to the top level
			widget.
		:param tuple args: Position arguments to provide when calling *method*.
		:param dict kwargs: Key word arguments to provide when calling *method*.
		"""
		utilities.assert_arg_type(method, str, 1)
		utilities.assert_arg_type(widget, (type(None), str), 2)
		self.widget = widget
		"""The name of the parent widget for this proxied child."""
		self.method = method
		"""The method of the parent widget that should be called to add the proxied child."""
		self.args = args or ()
		"""Arguments to append after the proxied child instance when calling :py:attr:`~.GladeProxyDestination.method`."""
		self.kwargs = kwargs or {}
		"""Key word arguments to append after the proxied child instance when calling :py:attr:`~.GladeProxyDestination.method`."""

	def __repr__(self):
		return "<{0} widget='{1}' method='{2}' >".format(self.__class__.__name__, self.widget, self.method)

class GladeProxy(object):
	"""
	A class that can be used to load another top level widget from the GTK
	builder data file in place of a child. This is useful for reusing small
	widgets as children in larger ones.
	"""
	__slots__ = ('destination',)
	name = None
	"""The string of the name of the top level widget to load."""
	children = ()
	"""A tuple of string names or :py:class:`.GladeProxy` instances listing the children widgets to load from the top level."""
	def __init__(self, destination):
		utilities.assert_arg_type(destination, GladeProxyDestination, 1)
		self.destination = destination
		"""A :py:class:`.GladeProxyDestination` instance describing how this proxied widget should be added to the parent."""

	def __repr__(self):
		return "<{0} name='{1}' destination={2} >".format(self.__class__.__name__, self.name, repr(self.destination))

class GladeGObjectMeta(type):
	"""
	A meta class that will update the :py:attr:`.GladeDependencies.name` value
	in the :py:attr:`.GladeGObject.dependencies` attribute of instances if no
	value is defined.
	"""
	assigned_name = type('assigned_name', (str,), {})
	"""A type subclassed from str that is used to define names which have been automatically assigned by this class."""
	def __init__(cls, *args, **kwargs):
		dependencies = getattr(cls, 'dependencies', None)
		if dependencies is not None:
			dependencies = copy.deepcopy(dependencies)
			setattr(cls, 'dependencies', dependencies)
			if isinstance(dependencies.name, (None.__class__, cls.assigned_name)):
				dependencies.name = cls.assigned_name(cls.__name__)
		super(GladeGObjectMeta, cls).__init__(*args, **kwargs)

# stylized metaclass definition to be Python 2.7 and 3.x compatible
class GladeGObject(GladeGObjectMeta('_GladeGObject', (object,), {})):
	"""
	A base object to wrap GTK widgets loaded from Glade data files. This
	provides a number of convenience methods for managing the main widget and
	child widgets. This class is meant to be subclassed by classes representing
	objects from the Glade data file.
	"""
	dependencies = GladeDependencies()
	"""A :py:class:`.GladeDependencies` instance which defines information for loading the widget from the GTK builder data."""
	config_prefix = ''
	"""A prefix to be used for keys when looking up value in the :py:attr:`~.GladeGObject.config`."""
	top_gobject = 'gobject'
	"""The name of the attribute to set a reference of the top level GObject to."""
	objects_persist = True
	"""Whether objects should be automatically loaded from and saved to the configuration."""
	def __init__(self, application):
		"""
		:param application: The parent application for this object.
		:type application: :py:class:`Gtk.Application`
		"""
		utilities.assert_arg_type(application, Gtk.Application, arg_pos=1)
		self.config = application.config
		"""A reference to the King Phisher client configuration."""
		self.application = application
		"""The parent :py:class:`Gtk.Application` instance."""
		self.logger = logging.getLogger('KingPhisher.Client.' + self.__class__.__name__)

		builder = Gtk.Builder()
		self.gtk_builder = builder
		"""A :py:class:`Gtk.Builder` instance used to load Glade data with."""

		top_level_dependencies = [gobject.name for gobject in self.dependencies.children if isinstance(gobject, GladeProxy)]
		top_level_dependencies.append(self.dependencies.name)
		if self.dependencies.top_level is not None:
			top_level_dependencies.extend(self.dependencies.top_level)
		builder.add_objects_from_file(which_glade(), top_level_dependencies)
		builder.connect_signals(self)
		gobject = builder.get_object(self.dependencies.name)
		setattr(self, self.top_gobject, gobject)
		if isinstance(gobject, Gtk.Window):
			gobject.set_transient_for(self.application.get_active_window())
			self.application.add_reference(self)
			if isinstance(gobject, Gtk.ApplicationWindow):
				application.add_window(gobject)
			if isinstance(gobject, Gtk.Dialog):
				gobject.set_modal(True)

		self.gobjects = utilities.FreezableDict()
		"""A :py:class:`~king_phisher.utilities.FreezableDict` which maps gobjects to their unique GTK Builder id."""
		self._load_child_dependencies(self.dependencies)
		self.gobjects.freeze()
		self._load_child_proxies()

		if self.objects_persist:
			self.objects_load_from_config()

	def _load_child_dependencies(self, dependencies):
		for child in dependencies.children:
			if isinstance(child, GladeProxy):
				self._load_child_dependencies(child)
				child = child.destination.widget
				if child is None:
					continue
			gobject = self.gtk_builder_get(child, parent_name=dependencies.name)
			# the following five lines ensure that the types match up, this is to enforce clean development
			gtype = child.split('_', 1)[0]
			if gobject is None:
				raise TypeError("gobject {0} could not be found in the glade file".format(child))
			elif gobject.__class__.__name__.lower() != gtype:
				raise TypeError("gobject {0} is of type {1} expected {2}".format(child, gobject.__class__.__name__, gtype))
			elif child in self.gobjects:
				raise ValueError("key: {0!r} is already in self.gobjects".format(child))
			self.gobjects[child] = gobject

	def _load_child_proxies(self):
		for child in self.dependencies.children or []:
			if not isinstance(child, GladeProxy):
				continue
			dest = child.destination
			widget = self.gtk_builder.get_object(self.dependencies.name) if dest.widget is None else self.gobjects[dest.widget]
			method = getattr(widget, dest.method)
			if method is None:
				raise ValueError("gobject {0} does not have method {1}".format(dest.widget, dest.method))
			src_widget = self.gtk_builder.get_object(child.name)
			self.logger.debug("setting proxied widget {0} via {1}.{2}".format(child.name, dest.widget, dest.method))
			method(src_widget, *dest.args, **dest.kwargs)

	@property
	def parent(self):
		return self.application.get_active_window()

	def get_entry_value(self, entry_name):
		"""
		Get the value of the specified entry then remove leading and trailing
		white space and finally determine if the string is empty, in which case
		return None.

		:param str entry_name: The name of the entry to retrieve text from.
		:return: Either the non-empty string or None.
		:rtype: None, str
		"""
		text = self.gobjects['entry_' + entry_name].get_text()
		text = text.strip()
		if not text:
			return None
		return text

	def gtk_builder_get(self, gobject_id, parent_name=None):
		"""
		Find the child GObject with name *gobject_id* from the GTK builder.

		:param str gobject_id: The object name to look for.
		:param str parent_name: The name of the parent object in the builder data file.
		:return: The GObject as found by the GTK builder.
		:rtype: :py:class:`GObject.Object`
		"""
		parent_name = parent_name or self.dependencies.name
		gtkbuilder_id = "{0}.{1}".format(parent_name, gobject_id)
		self.logger.debug('loading GTK builder object with id: ' + gtkbuilder_id)
		return self.gtk_builder.get_object(gtkbuilder_id)

	def objects_load_from_config(self):
		"""
		Iterate through :py:attr:`.gobjects` and set the GObject's value
		from the corresponding value in the :py:attr:`~.GladeGObject.config`.
		"""
		for gobject_id, gobject in self.gobjects.items():
			if '_' not in gobject_id:
				continue
			gtype, config_name = gobject_id.split('_', 1)
			config_name = self.config_prefix + config_name
			if gtype not in GOBJECT_PROPERTY_MAP:
				continue
			value = self.config.get(config_name)
			if value is None:
				continue
			if isinstance(GOBJECT_PROPERTY_MAP[gtype], (list, tuple)):
				GOBJECT_PROPERTY_MAP[gtype][0](gobject, value)
			else:
				gobject.set_property(GOBJECT_PROPERTY_MAP[gtype], value)

	def objects_save_to_config(self):
		for gobject_id, gobject in self.gobjects.items():
			if not '_' in gobject_id:
				continue
			gtype, config_name = gobject_id.split('_', 1)
			config_name = self.config_prefix + config_name
			if not gtype in GOBJECT_PROPERTY_MAP:
				continue
			self.config[config_name] = gobject_get_value(gobject, gtype)

	# forwarded methods
	def destroy(self):
		"""Call :py:meth:`~Gtk.Widget.destroy` on the top-level GTK Widget."""
		getattr(self, self.top_gobject).destroy()

	def hide(self):
		"""Call :py:meth:`~Gtk.Widget.hide` on the top-level GTK Widget."""
		getattr(self, self.top_gobject).hide()

	def show(self):
		"""Call :py:meth:`~Gtk.Widget.show` on the top-level GTK Widget."""
		getattr(self, self.top_gobject).show()

	def show_all(self):
		"""Call :py:meth:`~Gtk.Widget.show_all` on the top-level GTK Widget."""
		getattr(self, self.top_gobject).show_all()

class FileMonitor(object):
	"""Monitor a file for changes."""
	def __init__(self, path, on_changed):
		"""
		:param str path: The path to monitor for changes.
		:param on_changed: The callback function to be called when changes are detected.
		:type on_changed: function
		"""
		self.logger = logging.getLogger('KingPhisher.Utility.FileMonitor')
		self.on_changed = on_changed
		self.path = path
		self._gfile = Gio.file_new_for_path(path)
		self._gfile_monitor = self._gfile.monitor(Gio.FileMonitorFlags.NONE, None)
		self._gfile_monitor.connect('changed', self.cb_changed)
		self.logger.debug('starting file monitor for: ' + path)

	def __del__(self):
		self.stop()

	def stop(self):
		"""Stop monitoring the file."""
		if self._gfile_monitor.is_cancelled():
			return
		self._gfile_monitor.cancel()
		self.logger.debug('cancelled file monitor for: ' + self.path)

	def cb_changed(self, gfile_monitor, gfile, gfile_other, gfile_monitor_event):
		self.logger.debug("file monitor {0} received event: {1}".format(self.path, gfile_monitor_event.value_name))
		self.on_changed(self.path, gfile_monitor_event)
