# Copyright 2011 Shadow Robot Company Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, time, rospy, rospkg

from rospy import loginfo, logerr, logdebug

from qt_gui.plugin import Plugin
from python_qt_binding import loadUi

import QtCore
from QtCore import Qt, QEvent, QObject
import QtGui
from QtGui import *

from sr_hand.Grasp import Grasp
from sr_hand.grasps_interpoler import GraspInterpoler
from sr_hand.grasps_parser import GraspParser

from sr_hand.shadowhand_ros import ShadowHand_ROS

class JointSelecter(QtGui.QWidget):
    """
    Select which joints to save in a new grasp
    """
    def __init__(self, parent, all_joints):
        QtGui.QWidget.__init__(self, parent=parent)
        self.frame = QtGui.QFrame()
        self.layout = QtGui.QGridLayout()
        self.checkboxes = []

        col = 0
        #vectors to set the correct row in the layout for each col
        rows = [0, 0, 0, 0, 0, 0]
        joint_names = all_joints.keys()
        joint_names.sort()
        for joint in joint_names:
            if "fj1" in joint.lower():
                continue
            if "fj2" in joint.lower():
                continue
            if "ff" in joint.lower():
                col = 0
            elif "mf" in joint.lower():
                col = 1
            elif "rf" in joint.lower():
                col = 2
            elif "lf" in joint.lower():
                col = 3
            elif "th" in joint.lower():
                col = 4
            else:
                col = 5

            row = rows[col]
            rows[col] = row + 1
            cb = QtGui.QCheckBox(str(joint), self.frame)
            self.checkboxes.append(cb)
            self.layout.addWidget(cb, row, col)

        self.frame.setLayout(self.layout)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.frame)
        self.frame.show()
        self.setLayout(layout)
        self.show()

    def get_selected(self):
        """
        Retrieve selected joints
        """
        joints = []
        for cb in self.checkboxes:
            if cb.isChecked():
                joints.append(str(cb.text()))

        return joints

    def select_all(self):
        """
        Select all joints
        """
        for cb in self.checkboxes:
            cb.setChecked(True)

    def deselect_all(self):
        """
        Unselect all joints
        """
        for cb in self.checkboxes:
            cb.setChecked(False)

class GraspSaver(QtGui.QDialog):
    """
    Save a new grasp from the current joints positions.
    """
    def __init__(self, parent, all_joints, plugin_parent):
        QtGui.QDialog.__init__(self, parent)
        self.plugin_parent = plugin_parent
        self.all_joints = all_joints
        self.setModal(True)
        self.setWindowTitle("Save Grasp")

        self.grasp_name = ""

        self.upper_frame = QtGui.QFrame()
        self.upper_layout = QtGui.QHBoxLayout()
        label_name = QtGui.QLabel()
        label_name.setText("Grasp Name: ")
        name_widget = QtGui.QLineEdit()
        self.upper_frame.connect(name_widget, QtCore.SIGNAL('textChanged(QString)'), self.name_changed)

        self.upper_layout.addWidget(label_name)
        self.upper_layout.addWidget(name_widget)
        self.upper_frame.setLayout(self.upper_layout)

        select_all_frame = QtGui.QFrame()
        select_all_layout = QtGui.QHBoxLayout()
        btn_select_all = QtGui.QPushButton(select_all_frame)
        btn_select_all.setText("Select All")
        select_all_layout.addWidget(btn_select_all)
        self.connect(btn_select_all, QtCore.SIGNAL("clicked()"), self.select_all)
        btn_deselect_all = QtGui.QPushButton(select_all_frame)
        btn_deselect_all.setText("Deselect All")
        select_all_layout.addWidget(btn_deselect_all)
        self.connect(btn_deselect_all, QtCore.SIGNAL("clicked()"), self.deselect_all)
        select_all_frame.setLayout(select_all_layout)

        self.joint_selecter = JointSelecter(self, self.all_joints)

        btn_frame = QtGui.QFrame()
        self.btn_ok = QtGui.QPushButton(btn_frame)
        self.btn_ok.setText("OK")
        self.btn_ok.setDisabled(True)
        self.connect(self.btn_ok, QtCore.SIGNAL("clicked()"), self.accept)
        btn_cancel = QtGui.QPushButton(btn_frame)
        btn_cancel.setText("Cancel")
        self.connect(btn_cancel, QtCore.SIGNAL("clicked()"), self.reject)

        btn_layout = QtGui.QHBoxLayout()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(btn_cancel)
        btn_frame.setLayout(btn_layout)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.upper_frame)
        self.layout.addWidget(select_all_frame)
        self.layout.addWidget(self.joint_selecter)
        self.layout.addWidget(btn_frame)

        self.setLayout(self.layout)
        self.show()

    def select_all(self):
        """
        Select all joints
        """
        self.joint_selecter.select_all()

    def deselect_all(self):
        """
        Unselect all joints
        """
        self.joint_selecter.deselect_all()

    def name_changed(self, name):
        self.grasp_name = name
        if self.grasp_name != "":
            self.btn_ok.setEnabled(True)
        else:
            self.btn_ok.setDisabled(True)

    def accept(self):
        """
        Save grasp for the selected joints
        """
        grasp = Grasp()
        grasp.grasp_name = self.grasp_name

        joints_to_save = self.joint_selecter.get_selected()
        if len(joints_to_save) == 0:
            joints_to_save = self.all_joints.keys()
        for joint_to_save in joints_to_save:
            grasp.joints_and_positions[joint_to_save] = self.all_joints[joint_to_save]

        self.plugin_parent.sr_lib.grasp_parser.write_grasp_to_file(grasp)
        self.plugin_parent.sr_lib.grasp_parser.refresh()

        self.plugin_parent.reloadGraspSig['int'].emit(1)

        QtGui.QDialog.accept(self)

class GraspChooser(QtGui.QWidget):
    """
    Choose a grasp from a list of grasps.
    """
    def __init__(self, parent, plugin_parent, title):
        QtGui.QWidget.__init__(self)
        self.plugin_parent = plugin_parent
        self.grasp = None
        self.title = QtGui.QLabel()
        self.title.setText(title)

    def draw(self):
        """
        Draw the gui and connect signals
        """
        self.frame = QtGui.QFrame(self)

        self.list = QtGui.QListWidget()
        first_item = self.refresh_list()
        self.connect(self.list, QtCore.SIGNAL('itemClicked(QListWidgetItem*)'), self.grasp_selected)

        self.connect(self.list, QtCore.SIGNAL('itemDoubleClicked(QListWidgetItem*)'), self.double_click)
        self.list.setViewMode(QtGui.QListView.ListMode)
        self.list.setResizeMode(QtGui.QListView.Adjust)
        self.list.setItemSelected(first_item, True)
        self.grasp_selected(first_item, first_time=True)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.list)

        ###
        # SIGNALS
        ##
        self.plugin_parent.reloadGraspSig['int'].connect(self.refresh_list)

        self.frame.setLayout(self.layout)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.frame)
        self.frame.show()
        self.setLayout(layout)
        self.show()

    def double_click(self, item):
        """ 
        Sends new targets to the hand from a dictionary mapping the name of the joint to the value of its target
        """
        self.grasp = self.plugin_parent.sr_lib.grasp_parser.grasps[str(item.text())]
        self.plugin_parent.sr_lib.sendupdate_from_dict(self.grasp.joints_and_positions)
        self.plugin_parent.set_reference_grasp()

    def grasp_selected(self, item, first_time=False):
        """
        grasp has been selected with a single click
        """
        self.grasp = self.plugin_parent.sr_lib.grasp_parser.grasps[str(item.text())]
        if not first_time:
            self.plugin_parent.grasp_changed()
            self.plugin_parent.set_reference_grasp()

    def refresh_list(self, value = 0):
        """
        refreash list of grasps
        """
        self.list.clear()
        first_item = None
        grasps = self.plugin_parent.sr_lib.grasp_parser.grasps.keys()
        grasps.sort()
        for grasp_name in grasps:
            item = QtGui.QListWidgetItem(grasp_name)
            if first_item == None:
                first_item = item
            self.list.addItem(item)
        return first_item

class GraspSlider(QtGui.QWidget):
    """
    Slide from one grasp to another.
    """
    def __init__(self, parent, plugin_parent):
        QtGui.QWidget.__init__(self, parent)
        self.plugin_parent = plugin_parent

    def draw(self):
        """
        Draw the gui and connect signals
        """
        self.frame = QtGui.QFrame(self)
        label_frame = QtGui.QFrame(self.frame)
        from_label = QtGui.QLabel()
        from_label.setText("From")
        ref_label = QtGui.QLabel()
        ref_label.setText("Reference")
        to_label = QtGui.QLabel()
        to_label.setText("To")
        label_layout = QtGui.QHBoxLayout()
        label_layout.addWidget(from_label)
        label_layout.addWidget(ref_label)
        label_layout.addWidget(to_label)

        label_frame.setLayout(label_layout)

        self.slider = QtGui.QSlider()
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.slider.setTickInterval(100)
        self.slider.setTickPosition(QSlider.TicksAbove)
        self.slider.setMinimum(-100)
        self.slider.setMaximum(100)

        self.connect(self.slider, QtCore.SIGNAL('valueChanged(int)'), self.changeValue)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(label_frame)
        self.layout.addWidget(self.slider)

        self.frame.setLayout(self.layout)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.frame)
        self.frame.show()
        self.setLayout(layout)
        self.show()

    def changeValue(self, value):
        """
        interpolate from the current grasp to new value
        """
        self.plugin_parent.interpolate_grasps(value)

class SrGuiGraspController(Plugin):
    """
    Main GraspController plugin Dock window.
    """

    reloadGraspSig = QtCore.pyqtSignal(int)

    def __init__(self, context):
        super(SrGuiGraspController, self).__init__(context)

        self.setObjectName('SrGuiGraspController')
        
        self.icon_dir = os.path.join(rospkg.RosPack().get_path('sr_visualization_icons'), '/icons')
        
        self.sr_lib   = ShadowHand_ROS()
        
        ui_file = os.path.join(rospkg.RosPack().get_path('sr_gui_grasp_controller'), 'uis', 'SrGuiGraspController.ui')
        self._widget     = QWidget()
        loadUi(ui_file, self._widget)
        context.add_widget(self._widget)

        self.current_grasp = Grasp()
        self.current_grasp.name = 'CURRENT_UNSAVED'
        self.grasp_interpoler_1 = None
        self.grasp_interpoler_2 = None

        self.layout = self._widget.layout

        subframe = QtGui.QFrame()
        sublayout = QtGui.QVBoxLayout()

        self.grasp_slider = GraspSlider(self._widget, self)
        sublayout.addWidget(self.grasp_slider)

        btn_frame = QtGui.QFrame()
        btn_layout = QtGui.QHBoxLayout()
        self.btn_save = QtGui.QPushButton()
        self.btn_save.setText("Save")
        self.btn_save.setFixedWidth(130)
        self.btn_save.setIcon(QtGui.QIcon(self.icon_dir + '/save.png'))
        btn_frame.connect(self.btn_save, QtCore.SIGNAL('clicked()'), self.save_grasp)
        btn_layout.addWidget(self.btn_save)
        btn_set_ref = QtGui.QPushButton()
        btn_set_ref.setText("Set Reference")
        btn_set_ref.setFixedWidth(130)
        btn_set_ref.setIcon(QtGui.QIcon(self.icon_dir + '/iconHand.png'))
        btn_frame.connect(btn_set_ref, QtCore.SIGNAL('clicked()'), self.set_reference_grasp)
        btn_layout.addWidget(btn_set_ref)

        btn_frame.setLayout(btn_layout)
        sublayout.addWidget(btn_frame)
        subframe.setLayout(sublayout)

        self.grasp_from_chooser = GraspChooser(self._widget, self, "From: ")
        self.layout.addWidget(self.grasp_from_chooser)
        self.layout.addWidget(subframe)

        self.grasp_to_chooser = GraspChooser(self._widget, self, "To: ")
        self.layout.addWidget(self.grasp_to_chooser)

        self.grasp_slider.draw()
        self.grasp_to_chooser.draw()
        self.grasp_from_chooser.draw()

        time.sleep(0.2)
        self.set_reference_grasp()

    def shutdown_plugin(self):
        self._widget.close()
        self._widget.deleteLater()

    def save_settings(self, global_settings, perspective_settings):
        pass

    def restore_settings(self, global_settings, perspective_settings):
        pass

    def save_grasp(self):
        all_joints = self.sr_lib.read_all_current_positions()
        GraspSaver(self._widget, all_joints, self)

    def set_reference_grasp(self):
        """
        Set the current grasp as a reference for interpolation
        """
        self.current_grasp.joints_and_positions = self.sr_lib.read_all_current_positions()
        
        if self.current_grasp.joints_and_positions is None:
            #We try to activate ethercat hand again (detect if any controllers are running, and listen to them to extract the current position)
            self.sr_lib.activate_etherCAT_hand()
            #Some time to start receiving data
            rospy.sleep(0.5)
            self.current_grasp.joints_and_positions = self.sr_lib.read_all_current_positions()
        
            if self.current_grasp.joints_and_positions is None:
                QMessageBox.warning(self._widget, "Warning", "Could not read current grasp.\nCheck that the hand controllers are running.\nThen click \"Set Reference\"")
                return

        self.grasp_interpoler_1 = GraspInterpoler(self.grasp_from_chooser.grasp, self.current_grasp)
        self.grasp_interpoler_2 = GraspInterpoler(self.current_grasp, self.grasp_to_chooser.grasp)

        self.grasp_slider.slider.setValue(0)

    def grasp_changed(self):
        """
        interpolate grasps from chosen to current one and from current to chosen
        hand controllers must be running and reference must be set
        """
        self.current_grasp.joints_and_positions = self.sr_lib.read_all_current_positions()
        
        if self.current_grasp.joints_and_positions is None:
            QMessageBox.warning(self._widget, "Warning", "Could not read current grasp.\nCheck that the hand controllers are running.\nThen click \"Set Reference\"")
            return
        
        self.grasp_interpoler_1 = GraspInterpoler(self.grasp_from_chooser.grasp, self.current_grasp)
        self.grasp_interpoler_2 = GraspInterpoler(self.current_grasp, self.grasp_to_chooser.grasp)

    def interpolate_grasps(self, value):
        """
        interpolate grasp from the current one to the one indicated by value
        or in the opposite direction if value < 0
        hand controllers must be running and reference must be set
        """
        if self.grasp_interpoler_1 is None \
            or self.grasp_interpoler_2 is None:
            QMessageBox.warning(self._widget, "Warning", "Could not read current grasp.\nCheck that the hand controllers are running.\nThen click \"Set Reference\"")
            return
        #from -> current
        if value < 0:
            targets_to_send = self.grasp_interpoler_1.interpolate(100 + value)
            self.sr_lib.sendupdate_from_dict(targets_to_send)
        else:   #current -> to
            targets_to_send = self.grasp_interpoler_2.interpolate(value)
            self.sr_lib.sendupdate_from_dict(targets_to_send)
