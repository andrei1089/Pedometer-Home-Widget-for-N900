COORD_FNAME = "/sys/class/i2c-adapter/i2c-3/3-001d/coord"
COORD_FNAME_SDK = "/home/andrei/pedometer-widget-0.1/date.txt"
LOGFILE = "/home/user/log_pedometer"
#time in ms between two accelerometer data reads
COORD_GET_INTERVAL = 25

COUNT_INTERVAL = 5

import logging
import gobject

logger = logging.getLogger(__name__)

class PedometerException(Exception):
    pass

class PedometerReader(object):
    def get(self):
        f = open(self.COORD_FNAME, 'r')
        coords = [int(w) for w in f.readline().split()]
        f.close()
        return coords

class Pedometer(object):
    is_running = False
    callback = None
    current_walk = Walk()
    config = Config()
    reader = PedometerReader()

    def __init__(self, callback=None):
        self.callback = callback


    def start(self):
        if self.is_running:
            return PedometerException('Walk already in progress')
        logger.debug('Walk started')
        self.is_running = True
        gobject.idle_add(self._run)

    def stop(self):
        if not self.is_running:
            return PedometerException('No walk in progress')
        self.is_running = False

    def _run(self, callback_finished=None):
        self.coords = [[], [], []]
        self.stime = time.time()
        self.t = []
        gobject.timeout_add(utils.COORD_GET_INTERVAL, 
                    self._read_coords,
                    callback_finished)
        return False

    def _read_coords(self, callback):
        x, y, z = self.reader.get()
        logger.debug('New coords: %s %s %s' % (x, y, z)

        self.coords[0].append(int(x))
        self.coords[1].append(int(y))
        self.coords[2].append(int(z))
        now = time.time() - self.stime
        self.t.append(now)

        if self.t[-1] > utils.INTERVAL_LENGTH or not self.is_running:
            gobject.idle_add(self._stop_interval, callback)
            return False
        return True

    def _number_steps(self):
        pass

    def _stop_interval(self, callback):
        steps = self._number_steps()
        logger.info('Number of steps detected for last interval: %d' % steps)

        if self.is_running:
            gobject.idle_add(self.run)

        return False



