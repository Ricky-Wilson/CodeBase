built_modules = list(name for name in
    "Core;Gui;Widgets;PrintSupport;Sql;Network;Test;Concurrent;X11Extras;Xml;XmlPatterns;Help;Multimedia;MultimediaWidgets;OpenGL;Positioning;Location;Qml;Quick;QuickWidgets;Script;ScriptTools;Sensors;TextToSpeech;Charts;Svg;UiTools;WebChannel;WebEngineCore;WebEngine;WebEngineWidgets;WebSockets;3DCore;3DRender;3DInput;3DLogic"
    .split(";"))

shiboken_library_soversion = str(5.11)
pyside_library_soversion = str(5.11)

version = "5.11.2"
version_info = (5, 11, 2, "", "")

__build_date__ = '2019-07-08T08:30:45+00:00'




# Timestamp used for snapshot build, which is part of snapshot package version.
__setup_py_package_timestamp__ = ''
