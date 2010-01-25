import gtk
import hildondesktop
import gobject
import os
import time
import hildon
import gnome.gconf as gconf

print "!!!!"
#gobject.threads_init()

PATH="/apps/pedometerhomewidget"
COUNTER=PATH+"/counter"
MODE=PATH+"/mode"
HEIGHT=PATH+"/height"

class PedometerHomePlugin(hildondesktop.HomePluginItem):
    button = None
    loader = None
    labelTimer = None
    labelLastCount = None
    labelTotalCount = None
    labelDistance = None
    labelAvgDistance = None

    pedometer = None
    startTime = None
    totalCounter = 0

    def __init__(self):

        gtk.gdk.threads_init()
        hildondesktop.HomePluginItem.__init__(self)

        self.client = gconf.client_get_default()
        try:
            self.totalCounter = self.client.get_int(COUNTER)
            self.mode = self.client.get_int(MODE)
            self.height = self.client.get_int(HEIGHT)
        except:
            self.client.set_int(COUNTER, 0)
            self.client.set_int(MODE, 0)
            self.client.set_int(HEIGHT, 0)
            self.totalCounter = 0
            self.mode = 0
            self.height = 0

        self.button = gtk.Button("Start")
        self.button.connect("clicked", self.button_clicked)

        self.labelTimer = gtk.Label("00:00:00")
        self.labelLastCount = gtk.Label("--")
        self.labelTotalCount = gtk.Label("%d steps" % self.totalCounter)
        self.labelDistance = gtk.Label("--")

        mainVBox = gtk.VBox(spacing=1)
        mainVBox.add(self.button)
        mainVBox.add(self.labelTimer)
        mainVBox.add(self.labelLastCount)
        mainVBox.add(self.labelTotalCount)
        mainVBox.add(self.labelDistance)

        mainVBox.show_all()
        self.add(mainVBox)

        self.connect("unrealize", self.close_requested)
        self.set_settings(True)
        self.connect("show-settings", self.show_settings)


    def show_settings(self, widget):
        def reset_total_counter(arg):
            widget.totalCounter = 0
            widget.labelTotalCount.set_label("%d steps" % widget.totalCounter)
            hildon.hildon_banner_show_information(self,"None", "Total counter was resetted")

        def selector_changed(selector, data):
            widget.mode = selector.get_active(0)
            widget.client.set_int(MODE, widget.mode)

        def selectorH_changed(selector, data):
            widget.height = selectorH.get_active(0)
            widget.client.set_int(HEIGHT, widget.height)

        dialog = gtk.Dialog()
        dialog.set_transient_for(self)
        dialog.set_title("Settings")

        dialog.add_button("OK", gtk.RESPONSE_OK)
        button = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        button.set_title("Reset total counter")
        button.set_alignment(0, 0.8, 1, 1)
        button.connect("clicked", reset_total_counter)

        selector = hildon.TouchSelector(text=True)
        selector.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selector.append_text("Walk")
        selector.append_text("Run")
        selector.connect("changed", selector_changed)

        modePicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        modePicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        modePicker.set_title("Select mode")
        modePicker.set_selector(selector)
        modePicker.set_active(widget.mode)

        selectorH = hildon.TouchSelector(text=True)
        selectorH.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorH.append_text("< 1.50 m")
        selectorH.append_text("1.50 - 1.65 m")
        selectorH.append_text("1.66 - 1.80 m")
        selectorH.append_text("1.81 - 1.95 m")
        selectorH.append_text(" > 1.95 m")
        selectorH.connect("changed", selectorH_changed)

        heightPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        heightPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        heightPicker.set_title("Select height")
        heightPicker.set_selector(selectorH)
        heightPicker.set_active(widget.height)

        dialog.vbox.add(button)
        dialog.vbox.add(modePicker)
        dialog.vbox.add(heightPicker)
        dialog.show_all()
        response = dialog.run()
        hildon.hildon_banner_show_information(self, "None", "You have to Stop/Start the counter to apply the new settings")
        dialog.destroy()

    def close_requested(self, widget):
        if self.pedometer is None:
            return

        self.pedometer.request_stop()
        if self.pedometer.isAlive():
            self.pedometer.join()

    def update_values(self, totalCurent, lastInterval):
        print "update"

        self.totalCounter += lastInterval
        dist = self.pedometer.get_distance(self.totalCounter)

        tdelta = time.time() - self.startTime
        hours = int(tdelta / 3600)
        tdelta -= 3600 * hours
        mins = int(tdelta / 60)
        tdelta -= 60 * mins
        secs = int(tdelta)

        strtime = "%.2d:%.2d:%.2d" % ( hours, mins, secs)

        self.labelTimer.set_label(strtime)
        self.labelLastCount.set_label(str(totalCurent) + " steps")
        self.labelTotalCount.set_label(str(self.totalCounter) + " steps")
        if dist >= 1000:
            self.labelDistance.set_label(str(dist/1000) + " km")
        else:
            self.labelDistance.set_label(str(dist) + " m")

    def button_clicked(self, button):
        print "button clicked"

        if self.pedometer is not None and self.pedometer.isAlive():
            #counter is running
            self.pedometer.request_stop()
            self.pedometer.join()
            self.client.set_int(COUNTER, self.totalCounter)
            self.button.set_label("Start")
        else:
            self.pedometer = PedoCounter(self.update_values)
            self.pedometer.set_mode(self.mode)
            self.pedometer.set_height(self.height)

            self.labelTimer.set_label("00:00:00")
            self.labelLastCount.set_label("0 steps")
            self.labelTotalCount.set_label("%d steps" % self.totalCounter)
            self.labelDistance.set_label("0 m")

            self.pedometer.start()
            self.startTime = time.time()
            self.button.set_label("Stop")

        print "button clicked finished"

hd_plugin_type = PedometerHomePlugin

# The code below is just for testing purposes.
# It allows to run the widget as a standalone process.
if __name__ == "__main__":
    import gobject
    gobject.type_register(hd_plugin_type)
    obj = gobject.new(hd_plugin_type, plugin_id="plugin_id")
    obj.show_all()
    gtk.main()



############### old pedometer.py ###
import math
import logging

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

    def setThreshold(self, value):
        self.MIN_THRESHOLD = value

    def setTimeSteps(self, value):
        self.MIN_TIME_STEPS = value

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
    COORD_FNAME_SDK = "/home/andrei/pedometer-widget-0.1/date.txt"
    COORD_GET_INTERVAL = 0.01
    COUNT_INTERVAL = 5

    STEP_LENGTH = 0.7

    MIN_THRESHOLD = 500
    MIN_TIME_STEPS = 0.5

    counter = 0
    stop_requested = False
    update_function = None

    def __init__(self, update_function = None):
        Thread.__init__(self)
        if not os.path.exists(self.COORD_FNAME):
            self.COORD_FNAME = self.COORD_FNAME_SDK

        self.update_function = update_function

    def set_mode(self, mode):
        #runnig, higher threshold to prevent fake steps
        if mode == 1:
            self.MIN_THRESHOLD = 600
            self.MIN_TIME_STEPS = 0.35
        #walking
        else:
            self.MIN_THRESHOLD = 500
            self.MIN_TIME_STEPS = 0.5

    #set height, will affect the distance
    def set_height(self, height_interval):
        if height_interval == 0:
            STEP_LENGTH = 0.5
        elif height_interval == 1:
            STEP_LENGTH = 0.6
        elif height_interval == 2:
            STEP_LENGTH = 0.7
        elif height_interval == 3:
            STEP_LENGTH = 0.8
        elif height_interval == 4:
            STEP_LENGTH = 0.9

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
        while not self.stop_requested and (len(t) == 0 or t[-1] < 5):
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

    def request_stop(self):
        self.stop_requested = True

    def run(self):
        logger.info("Thread started")
        while 1 and not self.stop_requested:
            last_cnt = self.start_interval()
            if self.update_function is not None:
                gobject.idle_add(self.update_function, self.counter, last_cnt)

        logger.info("Thread has finished")

    def get_distance(self, steps=None):
        if steps == None:
            steps = self.counter
        return self.STEP_LENGTH * steps;

