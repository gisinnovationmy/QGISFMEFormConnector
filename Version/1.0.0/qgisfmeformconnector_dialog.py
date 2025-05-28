# -------------------------------------------------------------------------------
# QGIS-FME Form Connector - Version 0.9.1
# -------------------------------------------------------------------------------
#
# A powerful plugin that bridges QGIS and FME, enabling seamless data transformation 
# and workflow automation between these platforms.
#
# Key Features:
# - Direct FME workspace execution from QGIS
# - Parameter management for FME workspaces
# - Automated GeoJSON data handling
# - Real-time execution status monitoring
#
# Developed by: GIS Innovation Sdn Bhd
# Contact: sales@gis.fm / mygis@gis.my
#
# Copyright 2025 GIS Innovation Sdn Bhd. All rights reserved.
# -------------------------------------------------------------------------------

import os
import traceback
from qgis.utils import iface
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTabWidget, QLabel, QSizePolicy, QToolButton, QMessageBox, QCheckBox,
    QLineEdit, QHBoxLayout, QTreeView, QSplitter, QFileSystemModel, QDialog, QFrame,
    QStyledItemDelegate, QScrollArea, QProgressBar, QPlainTextEdit, QAbstractItemView, QApplication
)
from qgis.PyQt.QtCore import Qt, QCoreApplication, QVariant, QEvent, pyqtSignal, QUrl, QTimer
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterFileDestination,
    QgsProcessingException,
    QgsVectorFileWriter,
    QgsProject,
    QgsProcessingParameterDefinition,
    QgsProcessing,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingOutputString,
    QgsProcessingFeedback,
    Qgis,
    QgsMessageLog,
    QgsFeatureRequest,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsProcessingUtils,
    QgsApplication
)
from qgis.gui import QgsProcessingParameterDefinitionDialog
from processing.gui.wrappers import WidgetWrapper
import re
import uuid
import xml.etree.ElementTree as ET
import time
from datetime import datetime
import subprocess
import configparser
import tempfile
import sys

class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title):
        super().__init__()
        self.setTitle("")  # Keep the QGroupBox title empty

        # Create the toggle button
        self.toggle_button = QToolButton(self)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.RightArrow)  # Start with the right arrow (collapsed)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.clicked.connect(self.toggle)

        # Create the layout for the group box
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.toggle_button)
        self.content = QWidget(self)
        self.content.setLayout(QVBoxLayout())
        self.content.setVisible(False)
        self.layout.addWidget(self.content)

    def toggle(self):
        if self.toggle_button.isChecked():
            self.toggle_button.setArrowType(Qt.DownArrow)  # Change to down arrow (expanded)
            self.content.setVisible(True)
        else:
            self.toggle_button.setArrowType(Qt.RightArrow)  # Change back to right arrow (collapsed)
            self.content.setVisible(False)

    def add_widget(self, widget):
        self.content.layout().addWidget(widget)

    def expand(self):
        """Expand the group box to show the content."""
        self.toggle_button.setArrowType(Qt.DownArrow)  # Change to down arrow (expanded)
        self.content.setVisible(True)
        self.toggle_button.setChecked(True)

class FMEFileLister(QWidget):
    directory_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.stored_command = None  # Store the current command
        self.is_loading_fmw = False
        
        # Set path for ini file
        self.ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qgisfmeConnector.ini')
        self.dialog = parent  # Store reference to the dialog
        self.is_loading_fmw = False  # Flag to track if we're loading an FMW file
        self.setLayout(self.build_ui())
        
    def filePath(self):
        return os.path.normpath(self.current_file) if self.current_file else ''

    def add_parameter(self, name, value, required=False):
        """Add a parameter to the parameters table."""
        row = self.user_parameters_table.rowCount()
        self.user_parameters_table.insertRow(row)
        
        # Parameter name (with * for required parameters)
        name_item = QTableWidgetItem(f"*{name}" if required else name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)  # Make name read-only
        self.user_parameters_table.setItem(row, 0, name_item)
        
        # Remove only the enclosing quotes if they exist, preserving any internal quotes
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"' and value.count('"') >= 2:
            # Check if the quotes are actually enclosing quotes and not part of the value
            inner_value = value[1:-1]
            if not (inner_value.startswith('"') or inner_value.endswith('"')):
                value = inner_value
        
        # Parameter value
        value_item = QTableWidgetItem(value)
        self.user_parameters_table.setItem(row, 1, value_item)
        
        # Adjust row height
        self.user_parameters_table.resizeRowToContents(row)
        
        # Update command display
        self.update_command_display()

    def build_ui(self):
        # Add modern styling to the entire application
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 9pt;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 5px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                font-weight: 500;
            }
            QTreeView {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QTreeView::item {
                height: 25px;
            }
            QTreeView::item:hover {
                background-color: #f5f5f5;
            }
            QTreeView::item:selected {
                background-color: #e3f2fd;
                color: #000000;
            }
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
            }
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #2196f3;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create a QTabWidget to hold multiple tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
            }
        """)

        # Create the main content tab
        main_content_tab = QWidget()
        main_content_layout = QVBoxLayout()
        main_content_layout.setSpacing(10)
        main_content_tab.setLayout(main_content_layout)
        
        # Add layer selection label and widget
        select_layer_label = QLabel("Select layer:")
        select_layer_label.setStyleSheet("font-weight: 500;")
        main_content_layout.addWidget(select_layer_label)
        try:
            from qgis.gui import QgsMapLayerComboBox
            self.layer_combo = QgsMapLayerComboBox()
            self.layer_combo.setMinimumWidth(250)
            main_content_layout.addWidget(self.layer_combo)

            # --- Set combo to the current active layer in QGIS ---
            from qgis.utils import iface
            current_layer = iface.activeLayer()
            if current_layer is not None:
                self.layer_combo.setLayer(current_layer)

            # --- Two-way sync with QGIS layer panel ---
            self._syncing_layer = False
            def on_combo_layer_changed(layer):
                if self._syncing_layer:
                    return
                self._syncing_layer = True
                try:
                    if layer is not None:
                        from qgis.utils import iface
                        iface.setActiveLayer(layer)
                finally:
                    self._syncing_layer = False
            self.layer_combo.layerChanged.connect(on_combo_layer_changed)

            from qgis.utils import iface
            def on_map_layer_changed(layer):
                if self._syncing_layer:
                    return
                self._syncing_layer = True
                try:
                    self.layer_combo.setLayer(layer)
                finally:
                    self._syncing_layer = False
            iface.layerTreeView().currentLayerChanged.connect(on_map_layer_changed)
        except ImportError:
            pass  # Fallback if not in QGIS environment

        # Add directory widget to main content tab
        directory_group = QGroupBox("Directory Navigation")
        directory_layout = QVBoxLayout()
        directory_layout.setSpacing(8)
        
        # Create address bar with modern styling
        address_widget = QWidget()
        address_layout = QHBoxLayout()
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(8)
        
        # Add "Location:" label with modern styling
        address_label = QLabel("Location:")
        address_label.setStyleSheet("font-weight: 500;")
        address_layout.addWidget(address_label)
        
        # Custom QLineEdit for address bar that knows about its FMEFileLister
        class AddressLineEdit(QLineEdit):
            def __init__(self, file_lister, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.file_lister = file_lister
                
            def keyPressEvent(self, event):
                if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    self.file_lister.navigate_to_address(event)
                else:
                    super().keyPressEvent(event)

        # Add address bar with modern styling and default value
        self.address_bar = AddressLineEdit(self)
        self.address_bar.setPlaceholderText("Enter path or use tree view to navigate...")
        self.address_bar.setText("")  # Empty default value
        self.address_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px 8px;
                background-color: #ffffff;
                min-height: 25px;
            }
            QLineEdit:focus {
                border: 1px solid #2196f3;
            }
        """)
        address_layout.addWidget(self.address_bar)
        address_widget.setLayout(address_layout)
        directory_layout.addWidget(address_widget)

        # Create tree view
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath('')  # Empty string shows all drives
        self.file_model.setNameFilters(['*.fmw'])
        self.file_model.setNameFilterDisables(False)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setRootIndex(self.file_model.index(''))  # Empty string for root shows all drives
        self.tree_view.setColumnWidth(0, 250)  # Name
        self.tree_view.setColumnWidth(1, 100)  # Size
        self.tree_view.setColumnWidth(2, 100)  # Type
        self.tree_view.setColumnWidth(3, 150)  # Date Modified
        self.tree_view.clicked.connect(self.on_tree_item_clicked)
        self.tree_view.setMinimumHeight(200)  # Set minimum height for better visibility
        
        directory_layout.addWidget(self.tree_view)
        directory_group.setLayout(directory_layout)
        main_content_layout.addWidget(directory_group)
        
        # Update status label with modern styling
        self.status_label = QLabel()
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-weight: 500;
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
            }
        """)
        main_content_layout.addWidget(self.status_label)
        
        # Group for Workspace Header Content with modern styling
        self.workspace_header_group = CollapsibleGroupBox("Workspace Header Content")
        self.header_text = QPlainTextEdit()
        self.header_text.setObjectName("header_text")
        self.header_text.setReadOnly(True)
        self.header_text.setStyleSheet("font-family: monospace;")
        self.header_text.setMinimumHeight(100)
        self.header_text.setMaximumHeight(200)
        self.workspace_header_group.add_widget(self.header_text)
        main_content_layout.addWidget(self.workspace_header_group)

        # Modern styling for tables
        table_style = """
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                font-weight: 500;
            }
        """

        # Group for Source Dataset Table
        self.source_group = CollapsibleGroupBox("Source Datasets")
        self.source_dataset_table = QTableWidget(0, 2)
        self.source_dataset_table.setHorizontalHeaderLabels(["Dataset Format Type", "Dataset Full Path"])
        self.source_dataset_table.setColumnWidth(0, 150)
        self.source_dataset_table.setColumnWidth(1, 200)
        self.source_dataset_table.horizontalHeader().setStretchLastSection(True)
        self.source_dataset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.source_dataset_table.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.source_dataset_table.setStyleSheet(table_style)
        self.source_dataset_table.setItemDelegate(CustomItemDelegate())  # Apply custom delegate
        self.source_dataset_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.source_dataset_table.itemChanged.connect(self.update_command_display)  # Only update display, don't trigger FMECommandLine
        self.source_group.add_widget(self.source_dataset_table)
        main_content_layout.addWidget(self.source_group)

        # Group for Destination Dataset Table
        self.dest_group = CollapsibleGroupBox("Destination Datasets")
        self.dest_dataset_table = QTableWidget(0, 2)
        self.dest_dataset_table.setHorizontalHeaderLabels(["Dataset Format Type", "Dataset Full Path"])
        self.dest_dataset_table.setColumnWidth(0, 150)
        self.dest_dataset_table.setColumnWidth(1, 200)
        self.dest_dataset_table.horizontalHeader().setStretchLastSection(True)
        self.dest_dataset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dest_dataset_table.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.dest_dataset_table.setStyleSheet(table_style)
        self.dest_dataset_table.setItemDelegate(CustomItemDelegate())  # Apply custom delegate
        self.dest_dataset_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.dest_dataset_table.itemChanged.connect(self.update_command_display)  # Only update display, don't trigger FMECommandLine
        self.dest_group.add_widget(self.dest_dataset_table)
        main_content_layout.addWidget(self.dest_group)

        # Group for User Parameters Table
        self.params_group = CollapsibleGroupBox("User Parameters")
        self.user_parameters_table = QTableWidget(0, 2)
        self.user_parameters_table.setHorizontalHeaderLabels(["Parameter Name", "Default Value"])
        self.user_parameters_table.setColumnWidth(0, 150)
        self.user_parameters_table.setColumnWidth(1, 200)
        self.user_parameters_table.horizontalHeader().setStretchLastSection(True)
        self.user_parameters_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_parameters_table.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.user_parameters_table.setStyleSheet(table_style)
        self.user_parameters_table.setItemDelegate(CustomItemDelegate())  # Apply custom delegate
        self.user_parameters_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.user_parameters_table.itemChanged.connect(self.update_command_display)  # Only update display, don't trigger FMECommandLine
        self.params_group.add_widget(self.user_parameters_table)
        main_content_layout.addWidget(self.params_group)
        
        # Create paths table
        self.paths_group = CollapsibleGroupBox("Paths")
        
        # Create paths table
        self.paths_table = QTableWidget()
        self.paths_table.setRowCount(1)  # Always one row
        self.paths_table.setColumnCount(2)
        self.paths_table.setHorizontalHeaderLabels(["FME Executable", "FMW File"])
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.paths_table.cellClicked.connect(self.handle_cell_click)
        self.paths_table.itemChanged.connect(self.update_command_display)  # Add update trigger for path changes
        self.paths_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 6px;
                border: none;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        self.paths_table.setMinimumHeight(60)
        self.paths_table.setMaximumHeight(60)
        
        # Initialize the table with empty items that are editable
        self.paths_table.setItem(0, 0, QTableWidgetItem(""))
        self.paths_table.setItem(0, 1, QTableWidgetItem(""))
        self.paths_table.item(0, 0).setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.paths_table.item(0, 1).setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable)
        
        # FME.exe path will be loaded later via QTimer
        
        self.paths_group.add_widget(self.paths_table)

        # Add button under the paths table to save fme.exe path
        self.save_fme_path_button = QPushButton("Save fme.exe Path")
        self.save_fme_path_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #000000;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px 10px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
                border-color: #2196f3;
            }
            QPushButton:pressed {
                background-color: #bbdefb;
            }
        """)
        self.save_fme_path_button.clicked.connect(self.save_fme_exe_path)
        self.paths_group.add_widget(self.save_fme_path_button)
        main_content_layout.addWidget(self.paths_group)
        
        # Expand the paths group by default so the button is visible
        self.paths_group.expand()
        
        # Now load the FME.exe path after all UI elements are ready
        # Using a longer delay to ensure UI is fully initialized
        QTimer.singleShot(300, self.load_fme_exe_path)
        
        # Add tabs to the QTabWidget
        self.tabs.addTab(main_content_tab, "Main Content")
        
        # Create About tab
        about_tab = QWidget()
        about_layout = QVBoxLayout()
        about_tab.setLayout(about_layout)
        
        # About content with HTML styling
        about_text = QLabel()
        about_text.setOpenExternalLinks(True)
        about_text.setWordWrap(True)
        about_text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        about_text.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.6;
                color: #333333;
                padding: 20px;
                background-color: white;
            }
        """)
        
        about_content = f"""
            <div style='text-align: center; margin-bottom: 20px;'>
                <h2 style='color: #2c3e50; margin-bottom: 5px;'>QGIS-FME Form Connector</h2>
                <p style='color: #7f8c8d; margin-top: 0;'>Version 1.0.0</p>
            </div>

            <p style='margin-bottom: 15px;'>
                The QGIS-FME Form Connector is a powerful plugin that bridges QGIS and FME, enabling seamless data transformation 
                and workflow automation between these platforms.
            </p>

            <p style='margin-bottom: 15px;'>
                <b>Key Features:</b>
                <ul style='margin-left: 20px;'>
                    <li>Direct FME workspace execution from QGIS</li>
                    <li>Parameter management for FME workspaces</li>
                    <li>Real-time execution status monitoring</li>
                </ul>
            </p>

            <p style='margin-bottom: 15px;'>
                <b>Developed by:</b> GIS Innovation Sdn Bhd<br>
                <b>Contact:</b> <a href='mailto:sales@gis.fm' style='color: #3498db; text-decoration: none;'>sales@gis.fm</a><br>
                <b>Website:</b> <a href='https://www.GIS.com.my' style='color: #3498db; text-decoration: none;'>www.GIS.com.my</a>
            </p>

            <p style='color: #95a5a6; font-size: 9pt; text-align: center; margin-top: 30px;'>
                2025 GIS Innovation Sdn Bhd. All rights reserved.
            </p>
        """
        
        about_text.setText(about_content)
        about_layout.addWidget(about_text)
        about_layout.addStretch()
        
        self.tabs.addTab(about_tab, "About")
        
        # Add tabs to layout
        layout.addWidget(self.tabs)

        # Load the saved FME.exe path after UI is fully initialized
        self.load_fme_exe_path()
        
        return layout

    def navigate_to_address(self, event=None):
        """Navigate to the path entered in the address bar."""
        path = self.address_bar.text()
        if os.path.exists(path) and os.path.isdir(path):
            index = self.file_model.index(path)
            self.tree_view.setCurrentIndex(index)
            self.tree_view.scrollTo(index)
            self.address_bar.setText(path)
            if event:
                event.accept()
        else:
            QMessageBox.warning(self, "Invalid Path", "The specified path does not exist or is not a directory.")
            if event:
                event.accept()

    def go_up_directory(self):
        """Navigate up one directory level"""
        current_path = self.address_bar.text()
        parent_path = os.path.dirname(current_path)
        if os.path.exists(parent_path):
            parent_index = self.tree_view.rootIndex()
            if current_path != "":
                current_index = self.file_model.index(current_path)
                parent_index = current_index.parent()
        
        if parent_index.isValid():
            path = self.file_model.filePath(parent_index)
            self.tree_view.setCurrentIndex(parent_index)
            self.tree_view.scrollTo(parent_index)
            self.on_tree_item_clicked(parent_index)
            self.address_bar.setText(path)
            self.directory_selected.emit(path)  # Emit only if it's a directory

    def on_tree_item_clicked(self, index):
        """Handle tree view item selection"""
        try:
            norm_path = self.file_model.filePath(index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error getting file path: {str(e)}")
            return
            
        if not isinstance(norm_path, str):
            QMessageBox.critical(self, "Error", f"Invalid file path: {norm_path}")
            return

        if os.path.isdir(norm_path):
            self.address_bar.setText(norm_path)
            self.selected_directory = norm_path
            self.directory_selected.emit(norm_path)  # Emit only if it's a directory
            self.check_folder_for_workspaces(norm_path)
            return  # Do nothing further when a folder is selected

        if norm_path.lower().endswith('.fmw'):
            fmw_path = norm_path  # Fix: define fmw_path for downstream code
            self.current_file = norm_path
            # Update the FMW path in the paths table (cell 0,1)
            self.paths_table.setItem(0, 1, QTableWidgetItem(norm_path))
            
            # Then update the dataset paths which will ensure proper temp paths
            self.update_dataset_paths()
            
            # Finally build and store the command
            self.stored_command = self.build_fme_command()
            
            # Get the current destination path from the table
            dest_path = ""
            if self.dest_dataset_table.rowCount() > 0:
                dest_path = self.dest_dataset_table.item(0, 1).text()
            
            # Update command panel with paths
            if hasattr(self.dialog, 'create_command_execution_panel'):
                self.dialog.create_command_execution_panel(self.stored_command, "", dest_path)
        else:
            self.current_file = None
            self.stored_command = None
        
        self.address_bar.setText(norm_path)

        if os.path.isdir(norm_path):
            self.selected_directory = norm_path
            self.directory_selected.emit(norm_path)  # Emit only if it's a directory
            self.check_folder_for_workspaces(norm_path)
        elif norm_path.lower().endswith('.fmw'):
            self.selected_directory = os.path.dirname(norm_path)
            
            # Check if workspace is compatible by checking parameters
            required_params = ["SourceDataset_GEOJSON", "DestDataset_GEOJSON"]
            found_params = []
            for row in range(self.user_parameters_table.rowCount()):
                param_name = self.user_parameters_table.item(row, 0).text()
                if param_name and param_name in required_params:
                    found_params.append(param_name)

            is_compatible = len(found_params) >= len(required_params)

            if hasattr(self, 'check_compatibility') and self.check_compatibility.isChecked() and not is_compatible:
                missing_params = [p for p in required_params if p not in found_params]
                self.set_status_label(f"Selected FMW file: {os.path.basename(norm_path)} (Incompatible: This workspace is missing the following required FME Workspace Parameters: {', '.join(missing_params)})", success=False)
            else:
                self.set_status_label(f"Selected FMW file: {os.path.basename(norm_path)}")
            
            # Clear existing parameters
            self.user_parameters_table.setRowCount(0)
            self.source_dataset_table.setRowCount(0)
            self.dest_dataset_table.setRowCount(0)
            
            # Set the current workspace
            self.current_file = norm_path
        
        # Update the FMW path in the paths table
        for row in range(self.paths_table.rowCount()):
            if self.paths_table.item(row, 0) and self.paths_table.item(row, 0).text().lower() == "fmw":
                self.paths_table.setItem(row, 1, QTableWidgetItem(norm_path))
                # Update the command display after setting the path
                self.update_command_display()
                break
        
        # Clear existing parameters
        self.user_parameters_table.setRowCount(0)
        self.source_dataset_table.setRowCount(0)
        self.dest_dataset_table.setRowCount(0)
        
        # Check workspace compatibility
        is_compatible, compatibility_message = self.check_workspace_compatibility(norm_path)
        
        with open(norm_path, 'r') as file:
            lines = file.readlines()

            header_lines = []
            source_dataset_lines = []
            dest_dataset_lines = []
            user_parameter_lines = []
            header_started = False
            command_line_found = False

            for index, line in enumerate(lines):
                if line.startswith("#! <WORKSPACE"):
                    header_started = True
                if header_started:
                    if line.startswith("#!   A0_PREVIEW_IMAGE"):
                        break
                    header_lines.append(line)

                if "SourceDataset" in line:
                    cleaned_line = line.replace("#          --", "").strip()
                    parts = cleaned_line.split(" ", 1)
                    if len(parts) == 2:
                        source_dataset_lines.append((parts[0], parts[1]))

                elif "DestDataset" in line:
                    cleaned_line = line.replace("#          --", "").strip()
                    parts = cleaned_line.split(" ", 1)
                    if len(parts) == 2:
                        dest_dataset_lines.append((parts[0], parts[1]))

                elif re.search(r"#\s+--", line) and "SourceDataset" not in line and "DestDataset" not in line:
                    cleaned_line = re.sub(r"#\s+--", "", line).strip()
                    parts = cleaned_line.split(" ", 1)
                    if len(parts) == 2:
                        user_parameter_lines.append((parts[0], parts[1]))

            # Set the workspace header content
            self.header_text.setPlainText("".join(header_lines))
            self.adjust_header_height()

            # Update tables
            for name, value in source_dataset_lines:
                row = self.source_dataset_table.rowCount()
                self.source_dataset_table.insertRow(row)
                self.source_dataset_table.setItem(row, 0, QTableWidgetItem("GEOJSON"))
                self.source_dataset_table.setItem(row, 1, QTableWidgetItem(value.strip('"').strip("'")))

            for name, value in dest_dataset_lines:
                row = self.dest_dataset_table.rowCount()
                self.dest_dataset_table.insertRow(row)
                self.dest_dataset_table.setItem(row, 0, QTableWidgetItem("GEOJSON"))
                self.dest_dataset_table.setItem(row, 1, QTableWidgetItem(value.strip('"').strip("'")))

            for name, value in user_parameter_lines:
                self.add_parameter(name, value)

            # Update dataset paths
            self.update_dataset_paths()
            
            # Update command display
            self.update_command_display()
            
            # Update status label with compatibility message if not compatible
            if not is_compatible:
                self.set_status_label(f"Selected FMW file: {os.path.basename(fmw_path)} ({compatibility_message})", success=False)
            else:
                self.set_status_label(f"Loaded workspace: {os.path.basename(fmw_path)}", success=True)
            
            # Reset the loading flag
            self.is_loading_fmw = False

    def update_dataset_paths(self):
        """Update the source and destination dataset paths with the correct filename format"""
        try:
            # Generate unique filenames
            input_filename, output_filename = self.generate_filename_pair()
            
            # Get QGIS temp folder
            temp_folder = QgsApplication.qgisSettingsDirPath() + "temp/"
                
            # Create full paths
            input_path = os.path.join(temp_folder, input_filename)
            output_path = os.path.join(temp_folder, output_filename)
            
            # Update source dataset table
            if self.source_dataset_table.rowCount() == 0:
                self.source_dataset_table.insertRow(0)
            self.source_dataset_table.setItem(0, 0, QTableWidgetItem("GEOJSON"))
            self.source_dataset_table.setItem(0, 1, QTableWidgetItem(input_path))
            
            # Update destination dataset table
            if self.dest_dataset_table.rowCount() == 0:
                self.dest_dataset_table.insertRow(0)
            self.dest_dataset_table.setItem(0, 0, QTableWidgetItem("GEOJSON"))
            self.dest_dataset_table.setItem(0, 1, QTableWidgetItem(output_path))
            
            # Update command display
            self.update_command_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error updating dataset paths: {str(e)}")

    def generate_filename_pair(self):
        """Generate a pair of input/output filenames with the format YYYYMMDD_xxxxx_line2_[input/output].geojson"""
        from datetime import datetime
        import random
        import string
        import os
        from qgis.core import QgsApplication

        # Get current date in YYYYMMDD format
        current_date = datetime.now().strftime("%Y%m%d")
        
        # Get QGIS temp folder
        temp_folder = QgsApplication.qgisSettingsDirPath() + "temp/"
        os.makedirs(temp_folder, exist_ok=True)
        
        # Generate random chars until we get a unique one
        while True:
            # Generate 5 random lowercase alphanumeric characters
            chars = string.ascii_lowercase + string.digits
            random_chars = ''.join(random.choice(chars) for _ in range(5))
            
            # Create base filename
            base_filename = f"{current_date}_{random_chars}_line2"
            
            # Generate input and output filenames
            input_filename = f"{base_filename}_input.geojson"
            output_filename = f"{base_filename}_output.geojson"
            
            # Check if files already exist in the temp directory
            input_path = os.path.join(temp_folder, input_filename)
            output_path = os.path.join(temp_folder, output_filename)
            
            # If neither file exists, we can use these names
            if not os.path.exists(input_path) and not os.path.exists(output_path):
                break
        
        return input_filename, output_filename

    def handle_cell_click(self, row, column):
        """Handle cell clicks in the paths table."""
        if column == 0:
            self.select_fme_exe(row, column)
        elif column == 1:
            self.select_workspace(row, column)

    def select_fme_exe(self, row, column):
        """Open file dialog to select the fme.exe file and update the cell with the selected path."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select FME Executable",
                "",
                "Executable Files (*.exe);;All Files (*.*)"
            )
            if file_path:
                # Ensure the item exists
                if not self.paths_table.item(row, column):
                    self.paths_table.setItem(row, column, QTableWidgetItem(""))
                # Update the FME executable path in the paths table WITHOUT quotes
                self.paths_table.item(row, column).setText(file_path)
                
                # Update command display
                self.update_command_display()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting FME executable: {str(e)}")

    def select_workspace(self, row, column):
        """Open file dialog to select the .fmw file and update the cell with the selected path."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select FMW File",
                "",
                "FMW Files (*.fmw);;All Files (*.*)"
            )
            if file_path:
                # Ensure the item exists
                if not self.paths_table.item(row, column):
                    self.paths_table.setItem(row, column, QTableWidgetItem(""))
                # Update the workspace path in the paths table with quotes
                quoted_path = f'"{file_path}"'
                self.paths_table.item(row, column).setText(quoted_path)
                

                # Update command display
                self.update_command_display()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting workspace: {str(e)}")

    def adjust_table_height(self, table):
        """Adjust the height of the table based on the number of rows."""
        if table.rowCount() > 0:
            height = table.horizontalHeader().height() + (table.rowHeight(0) * table.rowCount())
        else:
            height = table.horizontalHeader().height() + 2
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    def adjust_header_height(self):
        """Adjust the height of the header text box based on the number of lines."""
        line_count = self.header_text.document().lineCount()
        self.header_text.setFixedHeight(line_count * 20 + 20)  # Estimate height based on line count

    def update_command_display(self, item=None):
        """Update the command display text box with the current command."""
        # Try to find the command_text in the dialog
        command_text = None
        source_label = None
        dest_label = None
        
        if hasattr(self, 'dialog') and self.dialog:
            command_text = self.dialog.findChild(QPlainTextEdit, "command_text")
            if not command_text and hasattr(self.dialog, 'command_text'):
                command_text = self.dialog.command_text
            
            # Find source and destination labels
            source_label = self.dialog.findChild(QLabel, "source_label")
            if not source_label and hasattr(self.dialog, 'source_label'):
                source_label = self.dialog.source_label
                
            dest_label = self.dialog.findChild(QLabel, "dest_label")
            if not dest_label and hasattr(self.dialog, 'dest_label'):
                dest_label = self.dialog.dest_label
        
        # If still not found, try to find it in the main window
        if not command_text:
            command_text = self.findChild(QPlainTextEdit, "command_text")
        
        # If still not found, try to find it in the parent window
        if not command_text and self.parent():
            command_text = self.parent().findChild(QPlainTextEdit, "command_text")
            if not command_text and hasattr(self.parent(), 'command_text'):
                command_text = self.parent().command_text
                
            # Find source and destination labels in parent
            if not source_label:
                source_label = self.parent().findChild(QLabel, "source_label")
                if not source_label and hasattr(self.parent(), 'source_label'):
                    source_label = self.parent().source_label
                    
            if not dest_label:
                dest_label = self.parent().findChild(QLabel, "dest_label")
                if not dest_label and hasattr(self.parent(), 'dest_label'):
                    dest_label = self.parent().dest_label
        
        # Get source and destination paths from the tables
        source_path = ""
        dest_path = ""
        
        if self.source_dataset_table and self.source_dataset_table.rowCount() > 0:
            source_item = self.source_dataset_table.item(0, 1)
            if source_item and source_item.text():
                source_path = source_item.text()
                
        if self.dest_dataset_table and self.dest_dataset_table.rowCount() > 0:
            dest_item = self.dest_dataset_table.item(0, 1)
            if dest_item and dest_item.text():
                dest_path = dest_item.text()
        
        # Update command text
        if command_text:
            # Get the current command
            current_command = self.build_fme_command()
            if current_command:
                # Display the command as a single line with spaces
                command_text.setPlainText(current_command)
            else:
                command_text.setPlainText("")  # Clear the command text
                
        # Update source and destination labels
        if source_label and source_path:
            source_label.setText(f"Source: {source_path}")
            
        if dest_label and dest_path:
            dest_label.setText(f"Destination: {dest_path}")
            
    def build_fme_command(self):
        """Build the FME command with all parameters."""
        # Get paths from the paths table
        if not self.paths_table or self.paths_table.rowCount() == 0:
            return None
        
        # Get FME executable path from paths table
        fme_exe_item = self.paths_table.item(0, 0)
        fmw_file_item = self.paths_table.item(0, 1)
        
        if not fme_exe_item or not fmw_file_item:
            return None
        
        fme_exe_path = fme_exe_item.text().strip().strip('"')
        fmw_file_path = fmw_file_item.text().strip().strip('"')

        if not fme_exe_path or not fmw_file_path:
            return None

        # Quote only if needed (contains spaces)
        if ' ' in fme_exe_path:
            fme_exe_path = f'"{fme_exe_path}"'
        if ' ' in fmw_file_path:
            fmw_file_path = f'"{fmw_file_path}"'

        # Start building the command
        command_parts = [f'{fme_exe_path} {fmw_file_path}']
        
        # Add user parameters
        for row in range(self.user_parameters_table.rowCount()):
            param_name_item = self.user_parameters_table.item(row, 0)
            param_value_item = self.user_parameters_table.item(row, 1)
            
            if param_name_item and param_value_item and param_value_item.text():
                # Remove any asterisk from parameter name
                param_name = param_name_item.text().replace('*', '')
                param_value = param_value_item.text()
                
                # Check if the parameter value already has double quotes
                if param_value.startswith('"') and param_value.endswith('"'):
                    command_parts.append(f'--{param_name} {param_value}')
                else:
                    command_parts.append(f'--{param_name} "{param_value}"')
        
        # Add source and destination dataset parameters if they exist
        if self.source_dataset_table and self.source_dataset_table.rowCount() > 0:
            source_item = self.source_dataset_table.item(0, 1)
            if source_item and source_item.text():
                source_value = source_item.text()
                if source_value.startswith('"') and source_value.endswith('"'):
                    command_parts.append(f'--SourceDataset_GEOJSON {source_value}')
                else:
                    command_parts.append(f'--SourceDataset_GEOJSON "{source_value}"')
        
        if self.dest_dataset_table and self.dest_dataset_table.rowCount() > 0:
            dest_item = self.dest_dataset_table.item(0, 1)
            if dest_item and dest_item.text():
                dest_value = dest_item.text()
                if dest_value.startswith('"') and dest_value.endswith('"'):
                    command_parts.append(f'--DestDataset_GEOJSON {dest_value}')
                else:
                    command_parts.append(f'--DestDataset_GEOJSON "{dest_value}"')
        
        # Join all parts with spaces for a single-line command
        command = ' '.join(command_parts)
        
        return command

    def save_fme_exe_path(self):
        """Save the current FME.exe path to the ini file"""
        # Get the current FME.exe path from the table
        fme_exe_path = self.paths_table.item(0, 0).text()
        
        # Strip any quotes that might be in the path
        fme_exe_path = fme_exe_path.strip('"')
        
        if not fme_exe_path:
            QMessageBox.warning(self, "Warning", "No fme.exe path specified. Please select a valid fme.exe path first.")
            return
            
        # First check if the path as entered exists (Windows handles both slash types)
        if os.path.exists(fme_exe_path) and fme_exe_path.lower().endswith('fme.exe'):
            # Path is valid as-is
            pass
        else:
            # Try normalizing the path and check again
            normalized_path = os.path.normpath(fme_exe_path)
            if not os.path.exists(normalized_path) or not normalized_path.lower().endswith('fme.exe'):
                QMessageBox.warning(self, "Warning", "Invalid fme.exe path. Please select a valid fme.exe file.")
                return
            # Use the normalized path if the original doesn't work
            fme_exe_path = normalized_path
        
        # Save the path to the ini file
        config = configparser.ConfigParser()
        
        # Create the config file if it doesn't exist
        if not os.path.exists(self.ini_file_path):
            with open(self.ini_file_path, 'w') as f:
                pass
        
        # Read existing configuration if available
        config.read(self.ini_file_path)
        
        # Ensure the 'Paths' section exists
        if 'Paths' not in config:
            config['Paths'] = {}
            
        # Set the FME.exe path
        config['Paths']['fme_exe'] = fme_exe_path
        
        # Write to the ini file
        with open(self.ini_file_path, 'w') as f:
            config.write(f)
            
        QMessageBox.information(self, "Success", f"fme.exe path has been saved to {self.ini_file_path}")
    
    def load_fme_exe_path(self):
        """Load the saved FME.exe path from the ini file"""
        if not os.path.exists(self.ini_file_path):
            # No ini file exists yet
            return
            
        config = configparser.ConfigParser()
        config.read(self.ini_file_path)
        
        # Check if the Paths section and fme_exe key exist
        if 'Paths' in config and 'fme_exe' in config['Paths']:
            fme_exe_path = config['Paths']['fme_exe']
            
            # Strip any quotes that might be in the saved path
            fme_exe_path = fme_exe_path.strip('"')
            
            # Normalize path for consistent format (handle forward/backslashes)
            normalized_path = os.path.normpath(fme_exe_path)
            
            # Set the path in the table even if it doesn't exist yet (user might need to reconnect drive)
            if self.paths_table.item(0, 0):
                self.paths_table.item(0, 0).setText(fme_exe_path)  # Use original format for display
                
                # Only show warning if we're explicitly trying to save
                if not os.path.exists(normalized_path) and not hasattr(self, '_suppress_warnings'):
                    self._suppress_warnings = True  # Prevent recursive warnings
                    QTimer.singleShot(500, lambda: setattr(self, '_suppress_warnings', False))
                
            # Update command display if needed
            self.update_command_display()
    
    def FMECommandLine(self):
        """Method to display a simple dialog box with 'Hello World' and update command text."""
        # Only proceed if we're not currently loading an FMW file
        if not self.is_loading_fmw:
            # Update the command display and path labels
            self.update_command_display()
            # QMessageBox.information(self, "FME Command Line", "Hello World")
            
    def set_status_label(self, text, success=True):
        """Set the status label with appropriate styles."""
        if success:
            style = """
                QLabel {
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: 500;
                    background-color: #e8f5e9;
                    border: 1px solid #c8e6c9;
                    color: #2e7d32;
                }
            """
        else:
            style = """
                QLabel {
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: 500;
                    background-color: #ffebee;
                    border: 1px solid #ffcdd2;
                    color: #c62828;
                }
            """
        self.status_label.setText(text)
        self.status_label.setStyleSheet(style)

    def set_folder_status_label(self, text):
        """Set the folder status label with appropriate styles."""
        style = """
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-weight: 500;
                background-color: #fff9c4;
                border: 1px solid #ffeb3b;
                color: #6a1b9a;
            }
        """
        self.status_label.setText(text)
        self.status_label.setStyleSheet(style)

    def check_folder_for_workspaces(self, folder_path):
        """Check the selected folder for FMW workspaces and update the status label."""
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Invalid Folder", "Selected path is not a folder")
            return

        fmw_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.fmw')]
        if not fmw_files:
            self.set_folder_status_label("This folder has no workspaces in it")
        else:
            self.set_folder_status_label(f"This folder has {len(fmw_files)} workspaces")

    def check_required_parameters(self):
        """Check if required QGIS parameters exist in the parameter table."""
        required_params = ["SourceDataset_GEOJSON", "DestDataset_GEOJSON"]
        found_params = []
        
        for row in range(self.user_parameters_table.rowCount()):
            param_name = self.user_parameters_table.item(row, 0)
            if param_name and param_name.text().replace('*', '') in required_params:
                found_params.append(param_name.text().replace('*', ''))
        
        if len(found_params) < len(required_params):
            missing_params = [p for p in required_params if p not in found_params]
            current_text = self.status_label.text()
            if not current_text.endswith("(Incompatible)"):
                self.set_status_label(f"{current_text} (Incompatible: Missing required parameters: {', '.join(missing_params)})", success=False)
            
            # Clear all tables
            # self.paths_table.setRowCount(0)
            self.user_parameters_table.setRowCount(0)

    def update_directory_label(self, directory):
        """Update the directory label with the current directory."""
        self.directory_label.setText(directory)
        self.check_folder_for_workspaces(directory)

    def ensure_tmp_directory(self, directory):
        """Ensure the temporary directory exists within the working directory."""
        tmp_dir = os.path.join(directory, 'tmp')
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        return tmp_dir

    def open_directory(self, event):
        """Open the current directory in file explorer."""
        if self.selected_directory and os.path.exists(self.selected_directory):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.selected_directory))

    def load_working_directory(self):
        """Load the last working directory from the config file."""
        try:
            config = configparser.ConfigParser()
            if os.path.exists(self.config_file):
                config.read(self.config_file)
                if 'Settings' in config and 'WorkingDirectory' in config['Settings']:
                    directory = config['Settings']['WorkingDirectory']
                    if os.path.exists(directory):
                        self.selected_directory = directory
                        self.update_directory_label(directory)
                        self.check_folder_for_workspaces(directory)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error loading working directory: {str(e)}", "QGIS-FME Connector", Qgis.Warning)

    def save_working_directory(self):
        """Save the current working directory to the config file."""
        try:
            config = configparser.ConfigParser()
            if os.path.exists(self.config_file):
                config.read(self.config_file)
            
            if 'Settings' not in config:
                config['Settings'] = {}
            
            config['Settings']['WorkingDirectory'] = self.selected_directory
            
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error saving working directory: {str(e)}", "QGIS-FME Connector", Qgis.Warning)

    def check_folder_for_workspaces(self, folder_path):
        """Check the selected folder for FMW workspaces and update the status label."""
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Invalid Folder", "Selected path is not a folder")
            return

        fmw_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.fmw')]
        if not fmw_files:
            self.set_folder_status_label("This folder has no workspaces in it")
        else:
            self.set_folder_status_label(f"This folder has {len(fmw_files)} workspaces")

    def check_required_parameters(self):
        """Check if required QGIS parameters exist in the parameter table."""
        required_params = ["SourceDataset_GEOJSON", "DestDataset_GEOJSON"]
        found_params = []
        
        for row in range(self.user_parameters_table.rowCount()):
            param_name = self.user_parameters_table.item(row, 0)
            if param_name and param_name.text().replace('*', '') in required_params:
                found_params.append(param_name.text().replace('*', ''))
        
        if len(found_params) < len(required_params):
            missing_params = [p for p in required_params if p not in found_params]
            current_text = self.status_label.text()
            if not current_text.endswith("(Incompatible)"):
                self.set_status_label(f"{current_text} (Incompatible: Missing required parameters: {', '.join(missing_params)})", success=False)
            
            # Clear all tables
            # self.paths_table.setRowCount(0)
            self.user_parameters_table.setRowCount(0)

    def update_directory_label(self, directory):
        """Update the directory label with the current directory."""
        self.directory_label.setText(directory)
        self.check_folder_for_workspaces(directory)

    def ensure_tmp_directory(self, directory):
        """Ensure the temporary directory exists within the working directory."""
        tmp_dir = os.path.join(directory, 'tmp')
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        return tmp_dir

    def open_directory(self, event):
        """Open the current directory in file explorer."""
        if self.selected_directory and os.path.exists(self.selected_directory):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.selected_directory))

    def load_working_directory(self):
        """Load the last working directory from the config file."""
        try:
            config = configparser.ConfigParser()
            if os.path.exists(self.config_file):
                config.read(self.config_file)
                if 'Settings' in config and 'WorkingDirectory' in config['Settings']:
                    directory = config['Settings']['WorkingDirectory']
                    if os.path.exists(directory):
                        self.selected_directory = directory
                        self.update_directory_label(directory)
                        self.check_folder_for_workspaces(directory)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error loading working directory: {str(e)}", "QGIS-FME Connector", Qgis.Warning)

    def save_working_directory(self):
        """Save the current working directory to the config file."""
        try:
            config = configparser.ConfigParser()
            if os.path.exists(self.config_file):
                config.read(self.config_file)
            
            if 'Settings' not in config:
                config['Settings'] = {}
            
            config['Settings']['WorkingDirectory'] = self.selected_directory
            
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error saving working directory: {str(e)}", "QGIS-FME Connector", Qgis.Warning)

    def create_command_execution_panel(self, command, source_path, dest_path):
        """Create or update the right panel for command execution."""
        try:
            # Use stored command from FMEFileLister if available
            if hasattr(self.parent(), 'fmwf_file') and self.parent().fmwf_file.stored_command:
                command = self.parent().fmwf_file.stored_command
                
            # Show the right panel if it's hidden
            self.right_panel.setVisible(True)

            # Clear existing widgets from right panel
            while self.right_layout.count():
                child = self.right_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        
            # Create command display group
            command_group = QGroupBox("Command")
            command_layout = QVBoxLayout()
            
            # Command text display
            self.command_text = QPlainTextEdit()  # Store as class attribute
            self.command_text.setObjectName("command_text")
            self.command_text.setReadOnly(True)
            self.command_text.document().documentLayout().documentSizeChanged.connect(
                lambda: self.command_text.setMinimumHeight(
                    int(min(200, self.command_text.document().size().height() + 20))
                )
            )
            size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            size_policy.setHeightForWidth(False)
            self.command_text.setSizePolicy(size_policy)
            self.command_text.setStyleSheet("QPlainTextEdit { background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px; padding: 8px; }")
            command_layout.addWidget(self.command_text)
            command_group.setLayout(command_layout)
            self.right_layout.addWidget(command_group)
            
            # Create paths group
            paths_group = QGroupBox("Paths")
            paths_layout = QVBoxLayout()
            
            # Source path label (clickable)
            source_label = SafeClickLabel(f"Source: {source_path}")
            source_label.setWordWrap(True)
            source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            source_label.setCursor(Qt.IBeamCursor)
            source_label.setStyleSheet("QLabel { padding: 5px; }")
            paths_layout.addWidget(source_label)
            
            # Destination path label (clickable)
            dest_label = SafeClickLabel(f"Destination: {dest_path}")
            dest_label.setWordWrap(True)
            dest_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            dest_label.setCursor(Qt.IBeamCursor)
            dest_label.setStyleSheet("QLabel { padding: 5px; }")
            paths_layout.addWidget(dest_label)
            
            paths_group.setLayout(paths_layout)
            self.right_layout.addWidget(paths_group)
            
            # Create output group
            output_group = QGroupBox("Output")
            output_layout = QVBoxLayout()
            
            # Status label
            self.status_label = QLabel("Ready to execute")
            self.status_label.setObjectName("status_label")
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: 500;
                    background-color: #e8f5e9;
                    border: 1px solid #c8e6c9;
                    color: #2e7d32;
                }
            """)
            output_layout.addWidget(self.status_label)
            
            # Add checkbox for scratch layer (only one instance)
            self.scratch_layer_checkbox = QCheckBox("Results as Scratch Layer")
            self.scratch_layer_checkbox.setChecked(True)  # Checked by default
            self.scratch_layer_checkbox.setObjectName("scratch_layer_checkbox")
            self.scratch_layer_checkbox.setStyleSheet("""
                QCheckBox {
                    padding: 5px;
                }
            """)
            output_layout.addWidget(self.scratch_layer_checkbox)
            
            # Progress bar (initially hidden)
            progress_bar = QProgressBar()
            progress_bar.setObjectName("progress_bar")
            progress_bar.setTextVisible(False)
            progress_bar.hide()
            output_layout.addWidget(progress_bar)

            # Output text
            output_text = QPlainTextEdit()
            output_text.setObjectName("output_text")
            output_text.setReadOnly(True)
            output_text.setStyleSheet("font-family: monospace;")
            output_text.setMinimumHeight(150)
            output_layout.addWidget(output_text)

            output_group.setLayout(output_layout)
            self.right_layout.addWidget(output_group)
            
            # Execute button
            execute_button = QPushButton("Execute Command")
            execute_button.setStyleSheet("""
                QPushButton {
                    background-color: #1976d2;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            execute_button.clicked.connect(lambda: self.execute_fme_command(command, source_path, dest_path))
            self.right_layout.addWidget(execute_button)
            
            # Add stretch to push everything to the top
            self.right_layout.addStretch()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creating command execution panel: {str(e)}")

    def execute_fme_command(self, command, source_path, dest_path):
        """Execute the FME command and display output."""
        # Check if a workspace is selected
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please select a Workspace first.")
            return
        
        try:
            # Get the widgets from the right panel
            status_label = self.findChild(QLabel, "status_label")
            progress_bar = self.findChild(QProgressBar, "progress_bar")
            output_text = self.findChild(QPlainTextEdit, "output_text")
            
            # Show progress bar and update status
            progress_bar.show()
            self.set_status_label("Executing command...", True)
            
            # Clear previous output
            output_text.clear()
            
            # Create process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True
            )
            
            # Create a QTimer to check process output
            timer = QTimer()
            
            def check_output():
                # Read any new output
                output = process.stdout.readline()
                if output:
                    output_text.appendPlainText(output.strip())
                    QApplication.processEvents()
                
                # If process has finished
                if process.poll() is not None:
                    timer.stop()
                    progress_bar.hide()
                    
                    # Get any remaining output
                    remaining_output, errors = process.communicate()
                    if remaining_output:
                        output_text.appendPlainText(remaining_output.strip())
                    if errors:
                        output_text.appendPlainText("Errors:")
                        output_text.appendPlainText(errors.strip())
                    
                    # Check if the process was successful
                    if process.returncode == 0:
                        if os.path.exists(dest_path):
                            # Success - show green status
                            status_label.setStyleSheet("""
                                QLabel {
                                    padding: 8px;
                                    border-radius: 4px;
                                    font-weight: 500;
                                    background-color: #e8f5e9;
                                    border: 1px solid #c8e6c9;
                                    color: #2e7d32;
                                }
                            """)
                            status_label.setText("Translation completed successfully!")
                            
                            # Check if we should load as scratch layer or regular layer
                            if self.scratch_layer_checkbox.isChecked():
                                # Create a memory layer by copying features from the GeoJSON file
                                source_layer = QgsVectorLayer(dest_path, "temp_source", "ogr")
                                if not source_layer.isValid():
                                    QMessageBox.warning(self, "Warning", "Failed to load source GeoJSON file")
                                else:
                                    # Create an empty memory layer with same CRS and fields
                                    geometry_type = source_layer.geometryType()
                                    geom_str = "Point"
                                    if geometry_type == 1:  # Line
                                        geom_str = "LineString"
                                    elif geometry_type == 2:  # Polygon
                                        geom_str = "Polygon"
                                        
                                    memory_layer = QgsVectorLayer(f"{geom_str}?crs=" + source_layer.crs().authid(), "FME_Form_Output", "memory")
                                    
                                    # Copy fields from source layer
                                    memory_layer.dataProvider().addAttributes(source_layer.fields())
                                    memory_layer.updateFields()
                                    
                                    # Copy features directly through the provider (no editing needed)
                                    features = [f for f in source_layer.getFeatures()]
                                    memory_layer.dataProvider().addFeatures(features)
                                    
                                    # Add to project
                                    QgsProject.instance().addMapLayer(memory_layer)
                                    
                                    status_label.setText("Translation successful! Layer added to map as scratch layer.")
                                    self.fmwf_file.update_dataset_paths()
                            else:
                                # Load the physical GeoJSON file directly
                                layer = QgsVectorLayer(dest_path, "FME_Form_Output", "ogr")
                                if not layer.isValid():
                                    QMessageBox.warning(self, "Warning", "Failed to load GeoJSON file")
                                else:
                                    # Add to project
                                    QgsProject.instance().addMapLayer(layer)
                                    
                                    status_label.setText("Translation successful! Layer added to map from file.")
                                    self.fmwf_file.update_dataset_paths()
                        else:
                            # Failed - output file not found
                            status_label.setStyleSheet("""
                                QLabel {
                                    padding: 8px;
                                    border-radius: 4px;
                                    font-weight: 500;
                                    background-color: #ffebee;
                                    border: 1px solid #ffcdd2;
                                    color: #c62828;
                                }
                            """)
                            status_label.setText("Translation failed: Output file not found")
                    else:
                        # Failed - process error
                        status_label.setStyleSheet("""
                            QLabel {
                                padding: 8px;
                                border-radius: 4px;
                                font-weight: 500;
                                background-color: #ffebee;
                                border: 1px solid #ffcdd2;
                                color: #c62828;
                            }
                        """)
                        status_label.setText("Translation failed!")
            
            # Connect timer to check_output
            timer.timeout.connect(check_output)
            timer.start(100)  # Check every 100ms
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"An error occurred while executing the FME command:\n{str(e)}\n\nDetails:\n{error_details}")

    def is_fmw_file_selected(self):
        """Validate FMW file selection with comprehensive checks."""
        
        if not hasattr(self, 'fmwf_file') or not self.fmwf_file:
            return False
            
        path = self.fmwf_file.filePath()
        
        if not path:
            return False
            
        exists = os.path.isfile(path)
        
        if not exists:
            return False
            
        return True

    def show_warning(self, title, message):
        """Show a warning message box."""
        QMessageBox.warning(self, title, message)

    def update_command_panel(self):
        if self.is_fmw_file_selected():
            fmw_path = self.fmwf_file.filePath()
            command = self.fmwf_file.build_fme_command()
            self.create_command_execution_panel(command, "", "")
        else:
            self.show_warning("Warning", "Please select an FMW file first.")

    def validate_fmw_file(self):
        if not hasattr(self, 'fmw_file'):
            return False

        path = self.fmw_file.text()
        if not path:
            return False

        exists = os.path.exists(path)
        if not exists:
            return False

        return True

    def check_workspace_compatibility(self, fmw_path):
        """Check if the FMW workspace has the required parameters."""
        try:
            # Define required parameters
            required_params = ["SourceDataset_GEOJSON", "DestDataset_GEOJSON"]
            found_params = []
            
            # Read the workspace file
            with open(fmw_path, 'r') as file:
                content = file.read()
            
            # Check for each required parameter
            for param in required_params:
                if param in content:
                    found_params.append(param)
            
            # Check if all required parameters are found
            is_compatible = len(found_params) >= len(required_params)
            
            if not is_compatible:
                missing_params = [p for p in required_params if p not in found_params]
                message = f"Incompatible: Missing required parameters: {', '.join(missing_params)}"
            else:
                message = "Compatible"
            
            return is_compatible, message
            
        except Exception as e:
            return False, f"Error checking compatibility: {str(e)}"

class EnterKeyDelegate:
    """This class is no longer used, replaced by CustomItemDelegate"""
    pass

class CustomItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setMinimumWidth(200)
        editor.setMinimumHeight(60)
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.DisplayRole)
        editor.setPlainText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class CustomParametersWidget(WidgetWrapper):
    """Widget wrapper for the FME Form Connector."""
    
    def __init__(self, param, dialog, row=0, col=0, **kwargs):
        self._widget = None
        self._algorithm = None
        super().__init__(param, dialog, row, col, **kwargs)

    def createWidget(self):
        """Create the FME File Lister widget."""
        if not self._widget:
            self._widget = FMEFileLister()
            self._widget.directory_selected.connect(self.directory_changed)
            # If we already have an algorithm, set the widget
            if self._algorithm:
                self._algorithm.setWidget(self._widget)
        return self._widget

    def setParentAlgorithm(self, algorithm):
        """Set the parent algorithm."""
        self._algorithm = algorithm

    def directory_changed(self, directory):
        """Handle directory selection changes."""
        if directory and os.path.isdir(directory):
            if self._widget:
                self._widget.selected_directory = directory
                self._widget.address_bar.setText(directory)
                index = self._widget.file_model.index(directory)
                self._widget.tree_view.setCurrentIndex(index)
                self._widget.tree_view.scrollTo(index)
                # Ensure algorithm has the widget
                if self._algorithm:
                    self._algorithm.setWidget(self._widget)

        self.validate_fmw_file()
        
    def value(self):
        """Return the selected FME workspace file path."""
        if self._widget:
            current_index = self._widget.tree_view.currentIndex()
            if current_index.isValid():
                return self._widget.file_model.filePath(current_index)
        return None

    def save_fme_exe_path(self, path):
        """Save the FME.exe path to the ini file."""
        config = configparser.ConfigParser()
        config.read(self.ini_file_path)
        if not config.has_section('FME'):
            config.add_section('FME')
        config.set('FME', 'exe_path', path)
        with open(self.ini_file_path, 'w') as configfile:
            config.write(configfile)

    def load_fme_exe_path(self):
        """Load the saved FME.exe path from the ini file."""
        config = configparser.ConfigParser()
        config.read(self.ini_file_path)
        if config.has_section('FME') and config.has_option('FME', 'exe_path'):
            return config.get('FME', 'exe_path')
        return None

class FMEFormConnectorAlgorithm(QgsProcessingAlgorithm):
    """QGIS Processing Algorithm for FME integration."""
    
    WORKSPACE = 'WORKSPACE'
    OUTPUT = 'OUTPUT'
    INPUT_LAYER = 'INPUT_LAYER'
    INPUT_DIRECTORY = 'INPUT_DIRECTORY'
    OUTPUT_LAYER = 'OUTPUT_LAYER'
    OUTPUT_TEXT = 'OUTPUT_TEXT'
    
    def __init__(self):
        super().__init__()
        self._widget = None
    
    def createInstance(self):
        return FMEFormConnectorAlgorithm()
    
    def name(self):
        return 'fmeformconnector'
    
    def displayName(self):
        return self.tr('FME Form Connector')
    
    def group(self):
        return self.tr('FME Integration')
    
    def groupId(self):
        return 'fmeintegration'
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
    
    def setWidget(self, widget):
        """Set the widget instance."""
        self._widget = widget
    
    def initAlgorithm(self, config=None):
        """Initialize the algorithm's parameters."""
        
        # Input vector layer parameter
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LAYER,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        
        # FME workspace directory parameter
        input_directory = QgsProcessingParameterString(
            self.INPUT_DIRECTORY,
            self.tr('FME Workspace Directory')
        )
        input_directory.setMetadata({'widget_wrapper': {'class': CustomParametersWidget}})
        self.addParameter(input_directory)
        
        # Output layer parameter
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LAYER,
                self.tr('Output layer')
            )
        )
        
        # Processing log output
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_TEXT,
                self.tr('Processing log')
            )
        )

class QGISFMEFormConnectorDialog(QDialog):
    _instance = None  # Singleton instance for the dialog

    @classmethod
    def show_dialog(cls):
        if cls._instance is None:
            cls._instance = QGISFMEFormConnectorDialog()
        cls._instance.show()
        cls._instance.raise_()  # Bring the dialog to the front

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        # Ensure dialog stays on top of QGIS but not above other apps
        from qgis.utils import iface
        super().__init__(iface.mainWindow())
        self.setWindowFlags(Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)
        
        # Set path for ini file
        self.ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qgisfmeConnector.ini')
        
        # Install global exception handler for PyQt errors
        sys.excepthook = self.handle_exception
        
        self.setWindowTitle('QGIS - FME Form Connector')
        # self.setWindowModality(Qt.WindowModal)  # Removed: handled with NonModal and parent above
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        # self.setWindowFlags(Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)  # Now set above with WindowStaysOnTopHint
        self.resize(1200, 800)  # Wider default size for the horizontal layout
        
        # Create the main horizontal layout
        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)
        
        # Left panel - FME File Lister
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Add the FMEFileLister widget inside a QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.fmwf_file = FMEFileLister(self)
        scroll_area.setWidget(self.fmwf_file)
        left_layout.addWidget(scroll_area)

        # Add "Close" button to the left panel
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to the right
        close_button = QPushButton("Close")
        button_layout.addWidget(close_button)
        left_layout.addLayout(button_layout)
        
        # Right panel - Command Execution (always visible)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        # Add title label
        title_label = QLabel("FME Command Execution")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.right_layout.addWidget(title_label)
        
        # Create command display group
        command_group = QGroupBox("Command")
        command_layout = QVBoxLayout()
        
        # Command text display
        self.command_text = QPlainTextEdit()
        self.command_text.setObjectName("command_text")
        self.command_text.setReadOnly(True)
        self.command_text.document().documentLayout().documentSizeChanged.connect(
            lambda: self.command_text.setMinimumHeight(
                int(min(200, self.command_text.document().size().height() + 20))
            )
        )
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy.setHeightForWidth(False)
        self.command_text.setSizePolicy(size_policy)
        self.command_text.setStyleSheet("QPlainTextEdit { background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px; padding: 8px; }")
        command_layout.addWidget(self.command_text)
        command_group.setLayout(command_layout)
        self.right_layout.addWidget(command_group)
        
        # Remove the File Paths group entirely
        
        # Add status label
        self.status_label = QLabel("Ready to execute")
        self.status_label.setObjectName("status_label")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-weight: 500;
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                color: #2e7d32;
            }
        """)
        self.status_label.setWordWrap(True)
        self.right_layout.addWidget(self.status_label)

        # Add checkbox for scratch layer (only one instance)
        self.scratch_layer_checkbox = QCheckBox("Results as Scratch Layer")
        self.scratch_layer_checkbox.setChecked(True)  # Checked by default
        self.scratch_layer_checkbox.setObjectName("scratch_layer_checkbox")
        self.scratch_layer_checkbox.setStyleSheet("""
            QCheckBox {
                padding: 5px;
            }
        """)
        self.right_layout.addWidget(self.scratch_layer_checkbox)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.right_layout.addWidget(self.progress_bar)

        # Add output text area
        output_label = QLabel("Command Output:")
        self.right_layout.addWidget(output_label)
        
        self.output_text = QPlainTextEdit()
        self.output_text.setObjectName("output_text")
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("font-family: monospace;")
        self.output_text.setMinimumHeight(150)
        self.right_layout.addWidget(self.output_text)

        # Add Execute Command button
        execute_button = QPushButton("Execute Command")
        execute_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        execute_button.clicked.connect(lambda: self.execute_fme_command(self.command_text.toPlainText(), 
                                                                      "", ""))
        execute_button.setObjectName("execute_button")
        execute_button.setStyleSheet("padding: 8px 16px; background-color: #2980b9; color: white;")
        self.right_layout.addWidget(execute_button)
        
        # Add a splitter between the left and right panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([600, 600])  # Equal initial sizes
        
        # Add the splitter to the main layout
        main_layout.addWidget(splitter)
        
        # Connect the Close button
        close_button.clicked.connect(self.close)

    def handle_exception(self, exctype, value, tb):
        """Handle global exceptions."""
        import traceback
        error_details = traceback.format_exc()
        QMessageBox.critical(self, "Error", f"An error occurred:\n{str(value)}\n\nDetails:\n{error_details}")

    def create_command_execution_panel(self, command, source_path, dest_path):
        """Update the command execution panel with new values."""
        try:
            # Use stored command from FMEFileLister if available
            if hasattr(self.fmwf_file, 'stored_command') and self.fmwf_file.stored_command:
                command = self.fmwf_file.stored_command
                
            # Update the command text
            self.command_text.setPlainText(command)
            self.command_text.setReadOnly(False)  # Allow user to edit and paste
            
            # Update the path labels
            # self.source_label.setText(f"Source: {source_path}")
            # self.dest_label.setText(f"Destination: {dest_path}")
            
            # Update click handlers for path labels
            # if source_geojson:
            #     self.source_label.mouseReleaseEvent = lambda e: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(source_geojson)))
            # if dest_geojson:
            #     self.dest_label.mouseReleaseEvent = lambda e: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(dest_geojson)))
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error updating command panel: {str(e)}\n{error_details}")
        
    def execute_fme_command(self, command, source_path, dest_path):
        """Execute the FME command and display output."""
        # Check if a workspace is selected
        if not self.fmwf_file.current_file:
            QMessageBox.warning(self, "Warning", "Please select a Workspace first.")
            return
            
        try:
            # Get the widgets from the right panel
            status_label = self.findChild(QLabel, "status_label")
            progress_bar = self.findChild(QProgressBar, "progress_bar")
            output_text = self.findChild(QPlainTextEdit, "output_text")
            
            # Save active layer to source GeoJSON
            active_layer = iface.activeLayer()
            if not active_layer:
                QMessageBox.critical(self, "Error", "No active layer selected!")
                return
                
            # Get the FME command from the file lister
            fme_command = self.fmwf_file.build_fme_command()
            if not fme_command:
                QMessageBox.critical(self, "Error", "Failed to build FME command. Please ensure a valid workspace is selected.")
                return
            
            # Extract source and destination paths from the command
            source_match = re.search(r'--SourceDataset_GEOJSON\s+"([^"]+)"', fme_command)
            dest_match = re.search(r'--DestDataset_GEOJSON\s+"([^"]+)"', fme_command)
            
            if source_match:
                source_path = source_match.group(1)
            else:
                # Create temp directory if it doesn't exist
                temp_dir = QgsApplication.qgisSettingsDirPath() + "temp/"
                
                # Generate default source path if not found in command
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                layer_name = active_layer.name().lower().replace(" ", "_")
                source_path = os.path.join(temp_dir, f"{timestamp}_{layer_name}_input.geojson")
                
                # Add to command
                fme_command += f' --SourceDataset_GEOJSON "{source_path}"'
            
            if dest_match:
                dest_path = dest_match.group(1)
            else:
                # Create temp directory if it doesn't exist
                temp_dir = QgsApplication.qgisSettingsDirPath() + "temp/"
                
                # Generate default destination path if not found in command
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                layer_name = active_layer.name().lower().replace(" ", "_")
                dest_path = os.path.join(temp_dir, f"{timestamp}_{layer_name}_output.geojson")
                
                # Add to command
                fme_command += f' --DestDataset_GEOJSON "{dest_path}"'
            
            # Ensure parent directories exist
            os.makedirs(os.path.dirname(source_path), exist_ok=True)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Save to GeoJSON
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "GeoJSON"
            save_options.fileEncoding = "UTF-8"
            
            # Transform to EPSG:4326 if needed
            if active_layer.crs().authid() != 'EPSG:4326':
                save_options.ct = QgsCoordinateTransform(
                    active_layer.crs(),
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    QgsProject.instance()
                )
            
            # Write to GeoJSON using the newer API
            try:
                # Try using the newer API first
                error = QgsVectorFileWriter.writeAsVectorFormatV2(
                    active_layer,
                    source_path,
                    QgsProject.instance().transformContext(),
                    save_options
                )
                if error[0] != QgsVectorFileWriter.NoError:
                    raise Exception(f"Error code: {error[0]}")
            except Exception as e:
                # Fall back to the older API
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    active_layer,
                    source_path,
                    "UTF-8",
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    "GeoJSON"
                )
                
                if error[0] != QgsVectorFileWriter.NoError:
                    QMessageBox.critical(self, "Error", f"Failed to save GeoJSON: {error[0]}\nPath: {source_path}\nPlease check if the directory exists and is writable.")
                    return
                
            # Update the command text display
            self.command_text.setPlainText(fme_command)

            # Update status and show progress bar
            status_label.setText("Executing command...")
            progress_bar.show()
            
            # Clear previous output
            output_text.clear()
            
            # Create process
            process = subprocess.Popen(
                fme_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True
            )
            
            # Create a QTimer to check process output
            timer = QTimer()
            
            def check_output():
                # Read any new output
                output = process.stdout.readline()
                if output:
                    output_text.appendPlainText(output.strip())
                    QApplication.processEvents()
                
                # If process has finished
                if process.poll() is not None:
                    timer.stop()
                    progress_bar.hide()
                    
                    # Get any remaining output
                    remaining_output, errors = process.communicate()
                    if remaining_output:
                        output_text.appendPlainText(remaining_output.strip())
                    if errors:
                        output_text.appendPlainText("Errors:")
                        output_text.appendPlainText(errors.strip())
                    
                    # Check if the process was successful
                    if process.returncode == 0:
                        if os.path.exists(dest_path):
                            # Success - show green status
                            status_label.setStyleSheet("""
                                QLabel {
                                    padding: 8px;
                                    border-radius: 4px;
                                    font-weight: 500;
                                    background-color: #e8f5e9;
                                    border: 1px solid #c8e6c9;
                                    color: #2e7d32;
                                }
                            """)
                            status_label.setText("Translation completed successfully!")
                            
                            # Check if we should load as scratch layer or regular layer
                            if self.scratch_layer_checkbox.isChecked():
                                # Create a memory layer by copying features from the GeoJSON file
                                source_layer = QgsVectorLayer(dest_path, "temp_source", "ogr")
                                if not source_layer.isValid():
                                    QMessageBox.warning(self, "Warning", "Failed to load source GeoJSON file")
                                else:
                                    # Create an empty memory layer with same CRS and fields
                                    geometry_type = source_layer.geometryType()
                                    geom_str = "Point"
                                    if geometry_type == 1:  # Line
                                        geom_str = "LineString"
                                    elif geometry_type == 2:  # Polygon
                                        geom_str = "Polygon"
                                        
                                    memory_layer = QgsVectorLayer(f"{geom_str}?crs=" + source_layer.crs().authid(), "FME_Form_Output", "memory")
                                    
                                    # Copy fields from source layer
                                    memory_layer.dataProvider().addAttributes(source_layer.fields())
                                    memory_layer.updateFields()
                                    
                                    # Copy features directly through the provider (no editing needed)
                                    features = [f for f in source_layer.getFeatures()]
                                    memory_layer.dataProvider().addFeatures(features)
                                    
                                    # Add to project
                                    QgsProject.instance().addMapLayer(memory_layer)
                                    
                                    status_label.setText("Translation successful! Layer added to map as scratch layer.")
                                    self.fmwf_file.update_dataset_paths()
                            else:
                                # Load the physical GeoJSON file directly
                                layer = QgsVectorLayer(dest_path, "FME_Form_Output", "ogr")
                                if not layer.isValid():
                                    QMessageBox.warning(self, "Warning", "Failed to load GeoJSON file")
                                else:
                                    # Add to project
                                    QgsProject.instance().addMapLayer(layer)
                                    
                                    status_label.setText("Translation successful! Layer added to map from file.")
                                    self.fmwf_file.update_dataset_paths()
                        else:
                            # Failed - output file not found
                            status_label.setStyleSheet("""
                                QLabel {
                                    padding: 8px;
                                    border-radius: 4px;
                                    font-weight: 500;
                                    background-color: #ffebee;
                                    border: 1px solid #ffcdd2;
                                    color: #c62828;
                                }
                            """)
                            status_label.setText("Translation failed: Output file not found")
                    else:
                        # Failed - process error
                        status_label.setStyleSheet("""
                            QLabel {
                                padding: 8px;
                                border-radius: 4px;
                                font-weight: 500;
                                background-color: #ffebee;
                                border: 1px solid #ffcdd2;
                                color: #c62828;
                            }
                        """)
                        status_label.setText("Translation failed!")
            
            # Connect timer to check_output
            timer.timeout.connect(check_output)
            timer.start(100)  # Check every 100ms
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"An error occurred while executing the FME command:\n{str(e)}\n\nDetails:\n{error_details}")

    def is_fmw_file_selected(self):
        """Validate FMW file selection with comprehensive checks."""
        
        if not hasattr(self, 'fmwf_file') or not self.fmwf_file:
            return False
            
        path = self.fmwf_file.filePath()
        
        if not path:
            return False
            
        exists = os.path.isfile(path)
        
        if not exists:
            return False
            
        return True

    def show_warning(self, title, message):
        """Show a warning message box."""
        QMessageBox.warning(self, title, message)

    def update_command_panel(self):
        if self.is_fmw_file_selected():
            fmw_path = self.fmwf_file.filePath()
            command = self.fmwf_file.build_fme_command()
            self.create_command_execution_panel(command, "", "")
        else:
            self.show_warning("Warning", "Please select an FMW file first.")

    def validate_fmw_file(self):
        if not hasattr(self, 'fmw_file'):
            return False

        path = self.fmw_file.text()
        if not path:
            return False

        exists = os.path.exists(path)
        if not exists:
            return False

        return True

    def check_workspace_compatibility(self, fmw_path):
        """Check if the FMW workspace has the required parameters."""
        pass

    def load_as_scratch_layer(self, geojson_path):
        """Load a GeoJSON file as a memory layer in QGIS if the checkbox is checked,
        otherwise load it as a regular layer."""
        
        # Create a memory layer by copying features from the GeoJSON file
        source_layer = QgsVectorLayer(geojson_path, "temp_source", "ogr")
        if not source_layer.isValid():
            QMessageBox.warning(self, "Warning", "Failed to load source GeoJSON file")
            return
                
        # Create an empty memory layer with same CRS and fields
        memory_layer = QgsVectorLayer("Point?crs=" + source_layer.crs().authid(), "FME_Form_Output", "memory")
        
        # Copy fields from source layer
        for field in source_layer.fields():
            memory_layer.dataProvider().addAttributes([field])
        memory_layer.updateFields()
        
        # Copy features directly through the provider (no editing needed)
        features = [f for f in source_layer.getFeatures()]
        memory_layer.dataProvider().addFeatures(features)
        
        # Add to project
        QgsProject.instance().addMapLayer(memory_layer)
        
        # Update dataset paths after loading the layer
        self.fmwf_file.update_dataset_paths()
        
        # Update status
        self.status_label.setText("Layer loaded as scratch layer")
        
        # Update status styling
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-weight: 500;
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                color: #2e7d32;
            }
        """)

        # Emit signal to uncheck toggle after generating points
        self.closingPlugin.emit()

    def cancel(self):
        """Triggered when Cancel button is clicked."""
        # Emit signal to close plugin and uncheck toggle
        self.closingPlugin.emit()  

    def closeEvent(self, event):
        # Override close event to hide dialog instead of deleting it
        event.ignore()
        self.hide()
        self.closingPlugin.emit()  # Emit the signal to notify that the dialog is closed

    def load_as_scratch_layer(self, geojson_path):
        """Load a GeoJSON file as a memory layer in QGIS if the checkbox is checked,
        otherwise load it as a regular layer."""
        
        # Create a memory layer by copying features from the GeoJSON file
        source_layer = QgsVectorLayer(geojson_path, "temp_source", "ogr")
        if not source_layer.isValid():
            QMessageBox.warning(self, "Warning", "Failed to load source GeoJSON file")
            return
                
        # Create an empty memory layer with same CRS and fields
        memory_layer = QgsVectorLayer("Point?crs=" + source_layer.crs().authid(), "FME_Form_Output", "memory")
        
        # Copy fields from source layer
        for field in source_layer.fields():
            memory_layer.dataProvider().addAttributes([field])
        memory_layer.updateFields()
        
        # Copy features directly through the provider (no editing needed)
        features = [f for f in source_layer.getFeatures()]
        memory_layer.dataProvider().addFeatures(features)
        
        # Add to project
        QgsProject.instance().addMapLayer(memory_layer)
        
        # Update dataset paths after loading the layer
        self.fmwf_file.update_dataset_paths()
        
        # Update status
        self.status_label.setText("Layer loaded as scratch layer")
        
        # Update status styling
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-weight: 500;
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                color: #2e7d32;
            }
        """)

        # Emit signal to uncheck toggle after generating points
        self.closingPlugin.emit()