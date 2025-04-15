# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from PyQt5.QtWidgets import QToolBar

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .qgisfmeformconnector_dialog import QGISFMEFormConnectorDialog

import os.path


class qgisfmeformconnector:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'qgisfmeformconnector_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QGIS - FME Form Connector')

        self.pluginIsActive = False
        self.dlg = None

        self.custom_menu = None
        self.menu_bar = None
        self.action = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('qgisfmeformconnector', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            # Get all current actions in the vector menu
            menu_actions = self.iface.vectorMenu().actions()

            # Add the new action to the list
            menu_actions.append(action)

            # Sort the actions alphabetically by their text
            sorted_actions = sorted(menu_actions, key=lambda a: a.text().lower())

            # Clear the current actions and re-add them sorted
            self.iface.vectorMenu().clear()
            for sorted_action in sorted_actions:
                self.iface.vectorMenu().addAction(sorted_action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create menu entries and toolbar icons inside the QGIS GUI."""
        # Create top-level menu in the QGIS menubar
        self.menu_bar = self.iface.mainWindow().menuBar()
        self.custom_menu = QMenu(self.tr("FME Platform Connectors"), self.menu_bar)
        self.menu_bar.addMenu(self.custom_menu)
        
        # Check if "FMETools" toolbar already exists
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "FMETools")
        if self.toolbar is None:
            self.toolbar = self.iface.addToolBar("FMETools")
            self.toolbar.setObjectName("FMETools")
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        
        # Create the action (checkable toggle)
        self.action = QAction(QIcon(icon_path), self.tr('QGIS - FME Form Connector'), self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_panel)
        
        # Add to both the custom menu and toolbar
        self.custom_menu.addAction(self.action)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def toggle_panel(self, checked):
        """Toggle the visibility of the dialog based on the checked state."""
        if checked:
            self.run()

        else:
            # Hide the dialog if the action is unchecked
            if self.dlg:
                self.dlg.hide()

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dialog is closed"""

        #print "** CLOSING QGIS - FME Form Connector **"

        # disconnects
        self.dlg.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dialog is to remain
        # for reuse if plugin is reopened
        # when closing the dialog:
        # self.dlg = None

        self.pluginIsActive = False

    def unload(self):
        for action in self.actions:
            if self.custom_menu:
                self.custom_menu.removeAction(action)

        if self.menu_bar and self.custom_menu:
            self.menu_bar.removeAction(self.custom_menu.menuAction())

    #--------------------------------------------------------------------------

    def run(self):
        if not self.pluginIsActive:
            self.pluginIsActive = True

            # Connect signals only once
            if self.dlg is None:
                self.dlg = QGISFMEFormConnectorDialog._instance or QGISFMEFormConnectorDialog()
                QGISFMEFormConnectorDialog._instance = self.dlg
                self.dlg.closingPlugin.connect(self.onClosePlugin)
                self.dlg.closingPlugin.connect(self.uncheck_toggle)

        QGISFMEFormConnectorDialog.show_dialog()

    def uncheck_toggle(self):
        """Uncheck the toolbar toggle when the dialog is closed."""
        for action in self.actions:
            if action.isCheckable():
                action.setChecked(False)