import dbus
import logging

from pedometer import Pedometer

logger = logging.getLogger(__name__)

DBUS_INTERFACE = 'org.maemo.pedometer.Daemon'


class PedometerDaemon(dbus.service.Object):

    def __init__(self):
        logger.debug('Starting Pedometer daemon')
        dbus.service.Object.__init__(self)
        self.pedometer = Pedometer(current_changed_callback=self.emit_current_changed)

    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='b')
    def Start(self):
        logger.debug('New walk started')
        self.pedometer.start()

    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='b')
    def Stop(self):
        logger.debug('Walking stopped')
        self.pedometer.stop()

    @dbus.service.signal(DBUS_INTERFACE)
    def CurrentChanged(self):
        logger.debug('CurrentChanged signal emitted')
        return self.pedometer.get_current()

    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='s')
    def GetCurrent(self):
        if self.pedometer.is_running:
            return self.pedometer.get_current()
        else:
            return None

    @dbus.service.method(DBUS_INTERFACE, in_signature='sss', out_signature='as')
    def GetHistory(start_date, stop_date, group_by):


if __name__ == "__main__":
    parser = OptionParse()
    parser.add_option("--debug",
            dest="debug",
            default=False)

    args = parser.parse_args()[0]

    #TODO: set log level
