import math
import time
import logging
import gobject

from threading import Thread

logger = logging.getLogger("pedometer")
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


class PedoIntervalCounter:
    MIN_THRESHOLD = 500
    MIN_TIME_STEPS = 0.5
    x = []
    y = []
    z = []
    t = []

    #TODO: check if last detected step is at the end of the interval

    def __init__(self, coords, tval):
        self.x = coords[0]
        self.y = coords[1]
        self.z = coords[2]
        self.t = tval

    def calc_mean(self, vals):
        sum = 0
        for i in vals:
            sum+=i
        if len(vals) > 0:
            return sum / len(vals)
        return 0

    def calc_stdev(self, vals):
        rez = 0
        mean = self.calc_mean(vals)
        for i in vals:
            rez+=pow(abs(mean-i),2)
        return math.sqrt(rez/len(vals))

    def calc_threshold(self, vals):
        vmax = max(vals)
        vmin = min(vals)
        mean = self.calc_mean(vals)
        threshold = max (abs(mean-vmax), abs(mean-vmin))
        return threshold

    def count_steps(self, vals, t):
        threshold = self.MIN_THRESHOLD
        mean = self.calc_mean(vals)
        cnt = 0

        i=0
        while i < len(vals):
            if abs(vals[i] - mean) > threshold:
                cnt+=1
                ntime = t[i] + 0.5
                while i < len(vals) and t[i] < ntime:
                    i+=1
            i+=1
        return cnt

    def get_best_values(self, x, y, z):
        dev1 = self.calc_stdev(x)
        dev2 = self.calc_stdev(y)
        dev3 = self.calc_stdev(z)
        dev_max = max(dev1, dev2, dev3)

        if ( abs(dev1 - dev_max ) < 0.001):
            logger.info("X chosen as best axis, stdev %f" % dev1)
            return x
        elif (abs(dev2 - dev_max) < 0.001):
            logger.info("Y chosen as best axis, stdev %f" % dev2)
            return y
        else:
            logger.info("Z chosen as best axis, stdev %f" % dev3)
            return z

    def number_steps(self):
        vals = self.get_best_values(self.x, self.y, self.z)
        return self.count_steps(vals, self.t)

class PedoCounter(Thread):
    COORD_FNAME = "/sys/class/i2c-adapter/i2c-3/3-001d/coord"
    COORD_GET_INTERVAL = 0.01
    COUNT_INTERVAL = 5
    STEP_LENGTH = 0.5

    counter = 0
    update_function = None

    def __init__(self, update_function = None):
        Thread.__init__(self)
        self.update_function = update_function

    def get_rotation(self):
        f = open(self.COORD_FNAME, 'r')
        coords = [int(w) for w in f.readline().split()]
        f.close()
        return coords

    def reset_counter(self):
        counter = 0

    def get_counter(self):
        return counter

    def start_interval(self):
        logger.info("New interval started")
        stime = time.time()
        t=[]
        coords = [[], [], []]
        while len(t) == 0 or t[-1] < 5:
            x,y,z = self.get_rotation()
            coords[0].append(int(x))
            coords[1].append(int(y))
            coords[2].append(int(z))
            now = time.time()-stime
            t.append(now)
            time.sleep(self.COORD_GET_INTERVAL)
        pic = PedoIntervalCounter(coords, t)
        cnt = pic.number_steps()

        logger.info("Number of steps detected for last interval %d, number of coords: %d" % (cnt, len(t)))

        self.counter += cnt
        logger.info("Total number of steps : %d" % self.counter)
        return cnt

    def run(self):
        while 1:
            last_cnt = self.start_interval()
            if self.update_function is not None:
                gobject.idle_add(self.update_function, self.counter, last_cnt)

    def get_distance(self, steps=None):
        if steps == None:
            steps = self.counter
        return self.STEP_LENGTH * steps;




if __name__ == "__main__":
    a = PedoCounter()
    a.run()
