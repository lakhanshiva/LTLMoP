"""LTLMoP sensor handler for the JR platform.

Before using this, run:
roslaunch subtle_launch static-sim.launch

Mappings currently in use are from subtle_launch/launch/main.lauch:
      <rosparam param="id2name">
        {
        "195" : "bomb1",
        "131" : "bomb2",
        "139" : "badguy",
        "225" : "hostage",
        "169" : "user2"
        }
      </rosparam>

"""

import re
from threading import RLock

import numpy
import logging


class sensorHandler(object):
    """Report the robot's current sensor status."""

    NODE_NAME = 'sensor_controller'
    SENSOR_TOPIC = 'fiducial_scan'

    def __init__(self, proj, shared_data):  # pylint: disable=W0613

        self._name = type(self).__name__

        # Store reference to proj and pose handler
        self._pose_handler = proj.h_instance['pose']
        self._proj = proj

        # Initialize lock, current objects sensed, and list of objects to ignore
        self._id_fiducials = dict()
        self._disabled_items = set()
        self._currently_sensed = set()
        self._fake_sensed = set()
        self._sensor_lock = RLock()

        self._last_region = self._pose_handler.get_location()  # keep track of region we were in when last polled

    def _set_sensors(self, msg):
        """Reads current sensor status from the robot."""
        # Note: This callback is only triggered when something is being seen
        with self._sensor_lock:
            # Treat our last updated region as the current one, even if it's slightly
            # out-of-date. If we query a fresh location, we might just add fids
            # that will be deleted at an imminent boundary
            current_region = self._last_region

    def get_sensor(self, sensor_name, initial=False):
        """Report whether we currently see a fiducial of the requested type.

        sensor_name (string): The type of the fiducial to query.
        """
        current_region = self._pose_handler.get_location()

        with self._sensor_lock:
            if initial:
                self._last_region = current_region
                # initialize landmark detection
                return True
            else:
                if current_region != self._last_region:
                    # We've entered a new region since the last poll;
                    # reset our accumulated list of sensed objects
                    print "{}: Resetting sensors on region change.".format(self._name)
                    self._currently_sensed = set()
                    self._last_region = current_region

                # Return whether we have it
                return ((sensor_name in self._fake_sensed) or
                        (self.get_sensed_item(sensor_name) is not None))

    def disable_item(self, item):
        """Disable viewing of an item."""
        with self._sensor_lock:
            print "{}: Disabling sensing item {!r}.".format(self._name, item.id)
            self._disabled_items.add(item.id)

            # Let the GUI know to hide it
            self._proj.executor.postEvent("FID", [item.id, None])

    def get_sensed_item(self, name):
        """Return a fiducial matching a name, None if there is no match."""
        with self._sensor_lock:
            for item in self._currently_sensed - self._disabled_items:
                if _clean_item_id(item) == name:
                    return self._id_fiducials[item]
            else:
                return None

    def _get_all_sensors(self):
        """Return all things currently sensed.

        To be used for testing only.
        """
        with self._sensor_lock:
            return list(self._currently_sensed | self._fake_sensed)

    def set_action_done(self, action_name, value):
        """Set whether an action is done to the given value."""
        sensor_name = action_name + "_done"
        print "{}: Setting action sensor {!r} to {}.".format(self._name, sensor_name, value)
        if value:
            self._fake_sensed.add(sensor_name)
        else:
            try:
                self._fake_sensed.remove(sensor_name)
            except KeyError:
                # If it's already inactive, no problem.
                pass


def _clean_item_id(name):
    """Clean off any trailing numbers from an item's name."""
    return re.sub(r"\d+$", "", name)