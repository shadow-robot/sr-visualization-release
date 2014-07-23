# Copyright (c) 2011, Dirk Thomas, TU Darmstadt
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#   * Neither the name of the TU Darmstadt nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


import os
import rospy
import rospkg

from time import sleep

from qt_gui.plugin import Plugin
from python_qt_binding import loadUi

from QtGui import QMessageBox, QWidget, QIcon
from controller_manager_msgs.srv import ListControllers, SwitchController, LoadController
from sr_robot_msgs.srv import ChangeControlType
from sr_robot_msgs.msg import ControlType

class SrGuiChangeControllers(Plugin):
    """
    A rosgui plugin for loading the different controllers
    """
    ICON_DIR = os.path.join(rospkg.RosPack().get_path('sr_visualization_icons'), 'icons')
    CONTROLLER_ON_ICON = QIcon(os.path.join(ICON_DIR, 'green.png'))
    CONTROLLER_OFF_ICON = QIcon(os.path.join(ICON_DIR, 'red.png'))

    joints = ["ffj0", "ffj3", "ffj4",
              "mfj0", "mfj3", "mfj4",
              "rfj0", "rfj3", "rfj4",
              "lfj0", "lfj3", "lfj4", "lfj5",
              "thj1", "thj2", "thj3", "thj4", "thj5",
              "wrj1", "wrj2"]
    controllers = {"effort": ["sh_{}_effort_controller".format(joint) for joint in joints],
                   "position": ["sh_{}_position_controller".format(joint) for joint in joints],
                   "mixed": ["sh_{}_mixed_position_velocity_controller".format(joint) for joint in joints],
                   "velocity": ["sh_{}_velocity_controller".format(joint) for joint in joints],
                   "stop": []}
    managed_controllers = [cont for type_conts in controllers.itervalues() for cont in type_conts]

    def __init__(self, context):
        super(SrGuiChangeControllers, self).__init__(context)
        self.setObjectName('SrGuiChangeControllers')

        self._publisher = None
        self._widget = QWidget()

        ui_file = os.path.join(rospkg.RosPack().get_path('sr_gui_change_controllers'), 'uis', 'SrChangeControllers.ui')
        loadUi(ui_file, self._widget)
        self._widget.setObjectName('SrChangeControllersUi')
        context.add_widget(self._widget)

        #Setting the initial state of the controller buttons
        self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_mixed.setChecked(False)
        self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_effort.setChecked(False)
        self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_position.setChecked(False)
        self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_velocity.setChecked(False)

        #attaching the button press event to their actions
        self._widget.btn_stop.pressed.connect(self.on_stop_ctrl_clicked_)
        self._widget.btn_effort.pressed.connect(self.on_effort_ctrl_clicked_)
        self._widget.btn_position.pressed.connect(self.on_position_ctrl_clicked_)
        self._widget.btn_mixed.pressed.connect(self.on_mixed_ctrl_clicked_)
        self._widget.btn_velocity.pressed.connect(self.on_velocity_ctrl_clicked_)

        #check the correct control box, depending on PWM_CONTROL env variable
        if os.environ.get('PWM_CONTROL') in [None, '0']:
            self._widget.radioButtonTorque.setChecked(True)
            self._widget.radioButtonPWM.setChecked(False)
        else:
            self._widget.radioButtonTorque.setChecked(False)
            self._widget.radioButtonPWM.setChecked(True)

        self._widget.radioButtonTorque.toggled.connect(self.on_control_mode_radio_button_toggled_)
        self._widget.radioButtonPWM.toggled.connect(self.on_control_mode_radio_button_toggled_)

    def on_control_mode_radio_button_toggled_(self, checked):
        """
        Switch between FORCE, PWM modes
        We only react to the currently ON radio button event
        """
        if checked:
            change_type_msg = ChangeControlType()
            if self._widget.radioButtonTorque.isChecked():
                change_type_msg.control_type = ControlType.FORCE
                rospy.loginfo("Change Control mode to FORCE")
            else:
                change_type_msg.control_type = ControlType.PWM
                rospy.loginfo("Change Control mode to PWM")
            self.change_force_ctrl_type(change_type_msg)

    def on_stop_ctrl_clicked_(self):
        """
        Stop controller
        """
        self._widget.btn_stop.setEnabled(False)
        self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_mixed.setChecked(False)
        self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_effort.setChecked(False)
        self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_position.setChecked(False)
        self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
        self._widget.btn_velocity.setChecked(False)
        self.change_ctrl( "stop" )
        self._widget.btn_stop.setEnabled(True)

    def on_effort_ctrl_clicked_(self):
        """
        Effort controller selected
        """
        self._widget.btn_effort.setEnabled(False)
        if not self._widget.btn_effort.isChecked():
            self._widget.btn_effort.setIcon(self.CONTROLLER_ON_ICON)
            self._widget.btn_effort.setChecked(True)
            self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_position.setChecked(False)
            self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_mixed.setChecked(False)
            self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_velocity.setChecked(False)
            rospy.loginfo("Effort checked: " + str(self._widget.btn_effort.isChecked()))
            self.change_ctrl( "effort" )
        else:
            self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_effort.setChecked(False)
            rospy.loginfo("Effort checked: " + str(self._widget.btn_effort.isChecked()))
            self.change_ctrl( "stop" )
        self._widget.btn_effort.setEnabled(True)

    def on_position_ctrl_clicked_(self):
        """
        Position controller selected
        """
        self._widget.btn_position.setEnabled(False)
        if not self._widget.btn_position.isChecked():
            self._widget.btn_position.setIcon(self.CONTROLLER_ON_ICON)
            self._widget.btn_position.setChecked(True)
            self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_effort.setChecked(False)
            self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_mixed.setChecked(False)
            self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_velocity.setChecked(False)
            rospy.loginfo("Position checked: " + str(self._widget.btn_position.isChecked()))
            self.change_ctrl( "position" )
        else:
            self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_position.setChecked(False)
            rospy.loginfo("Position checked: " + str(self._widget.btn_position.isChecked()))
            self.change_ctrl( "stop" )
        self._widget.btn_position.setEnabled(True)

    def on_mixed_ctrl_clicked_(self):
        """
        Mixed controller selected
        """
        self._widget.btn_mixed.setEnabled(False)
        if not self._widget.btn_mixed.isChecked():
            self._widget.btn_mixed.setIcon(self.CONTROLLER_ON_ICON)
            self._widget.btn_mixed.setChecked(True)
            self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_effort.setChecked(False)
            self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_position.setChecked(False)
            self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_velocity.setChecked(False)
            rospy.loginfo("Mixed checked: " + str(self._widget.btn_mixed.isChecked()))
            self.change_ctrl( "mixed" )
        else:
            self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_mixed.setChecked(False)
            rospy.loginfo("Mixed checked: " + str(self._widget.btn_mixed.isChecked()))
            self.change_ctrl( "stop" )
        self._widget.btn_mixed.setEnabled(True)

    def on_velocity_ctrl_clicked_(self):
        """
        Velocity controller selected
        """
        self._widget.btn_velocity.setEnabled(False)
        if not self._widget.btn_velocity.isChecked():
            self._widget.btn_velocity.setIcon(self.CONTROLLER_ON_ICON)
            self._widget.btn_velocity.setChecked(True)
            self._widget.btn_effort.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_effort.setChecked(False)
            self._widget.btn_position.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_position.setChecked(False)
            self._widget.btn_mixed.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_mixed.setChecked(False)
            rospy.loginfo("Velocity checked: " + str(self._widget.btn_velocity.isChecked()))
            self.change_ctrl( "velocity" )
        else:
            self._widget.btn_velocity.setIcon(self.CONTROLLER_OFF_ICON)
            self._widget.btn_velocity.setChecked(False)
            rospy.loginfo("Velocity checked: " + str(self._widget.btn_velocity.isChecked()))
            self.change_ctrl( "stop" )
        self._widget.btn_velocity.setEnabled(True)

    def change_ctrl(self, controller):
        """
        Switch the current controller
        """
        success = True
        list_controllers = rospy.ServiceProxy('controller_manager/list_controllers', ListControllers)
        try:
            resp1 = list_controllers()
        except rospy.ServiceException:
            success = False

        if success:
            controllers_to_stop = [c.name for c in resp1.controller if c.state == "running" and c.name in self.managed_controllers]
            all_loaded_controllers = [c.name for c in resp1.controller]

            controllers_to_start = self.controllers[controller]

            load_controllers = None
            for load_control in controllers_to_start:
                if load_control not in all_loaded_controllers:
                    try:
                        load_controllers = rospy.ServiceProxy('controller_manager/load_controller', LoadController)
                        resp1 = load_controllers(load_control)
                    except rospy.ServiceException:
                        success = False
                    if not resp1.ok:
                        success = False

            switch_controllers = rospy.ServiceProxy('controller_manager/switch_controller', SwitchController)
            try:
                resp1 = switch_controllers(controllers_to_start, controllers_to_stop, SwitchController._request_class.BEST_EFFORT)
            except rospy.ServiceException:
                success = False

            if not resp1.ok:
                success = False

        if not success:
            rospy.logwarn("Failed to change some of the controllers. This is normal if this is not a 5 finger hand.")

    def change_force_ctrl_type(self, chng_type_msg):
        """
        Calls the service (realtime_loop/change_control_type) that allows to tell the driver (sr_robot_lib)
        which type of force control has to be sent to the motor:
            - torque demand (sr_robot_msgs::ControlType::FORCE)
            - PWM (sr_robot_msgs::ControlType::PWM)
        it will deactivate the Effort, Position, Mixed and Velocity buttons for 3 secs to allow hardware controllers to be updated
        """
        success = True
        change_control_type = rospy.ServiceProxy('realtime_loop/change_control_type', ChangeControlType)
        try:
            resp1 = change_control_type(chng_type_msg)
            if resp1.result.control_type != chng_type_msg.control_type:
                success = False
        except rospy.ServiceException:
            success = False

        # Disable buttons for 3 secs until motors change their parameters
        self._widget.btn_effort.setEnabled(False)
        self._widget.btn_position.setEnabled(False)
        self._widget.btn_mixed.setEnabled(False)
        self._widget.btn_velocity.setEnabled(False)
        sleep(3)
        self._widget.btn_effort.setEnabled(True)
        self._widget.btn_position.setEnabled(True)
        self._widget.btn_mixed.setEnabled(True)
        self._widget.btn_velocity.setEnabled(True)

        if not success:
            QMessageBox.warning(self._widget, "Warning", "Failed to change the control type.")

    def _unregisterPublisher(self):
        if self._publisher is not None:
            self._publisher.unregister()
            self._publisher = None

    def shutdown_plugin(self):
        self._unregisterPublisher()

    def save_settings(self, global_settings, perspective_settings):
        pass

    def restore_settings(self, global_settings, perspective_settings):
        pass
