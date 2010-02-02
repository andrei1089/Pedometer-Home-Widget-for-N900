#Pedometer Home Widget
#Author: Mirestean Andrei < andrei.mirestean at gmail.com >
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
import cairo
import hildondesktop
import gobject
import os
import time
import hildon
import gnome.gconf as gconf
from threading import Thread

#gobject.threads_init()
#gtk.gdk.threads_init()

PATH="/apps/pedometerhomewidget"
COUNTER=PATH+"/counter"
TIMER=PATH+"/timer"
MODE=PATH+"/mode"
HEIGHT=PATH+"/height"
UNIT=PATH+"/unit"
ASPECT=PATH+"/aspect"
LOGGING=PATH+"/logging"

ICONSPATH = "/opt/pedometerhomewidget/"

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
    LOGFILE = "/home/user/log_pedometer"
    COORD_GET_INTERVAL = 0.01
    COUNT_INTERVAL = 5

    STEP_LENGTH = 0.7

    MIN_THRESHOLD = 500
    MIN_TIME_STEPS = 0.5

    counter = 0
    stop_requested = False
    update_function = None
    logging = False

    mode = 0

    def __init__(self, update_function = None):
        Thread.__init__(self)
        if not os.path.exists(self.COORD_FNAME):
            self.COORD_FNAME = self.COORD_FNAME_SDK

        self.update_function = update_function

    def set_mode(self, mode):
        #runnig, higher threshold to prevent fake steps
        self.mode = mode
        if mode == 1:
            self.MIN_THRESHOLD = 650
            self.MIN_TIME_STEPS = 0.35
        #walking
        else:
            self.MIN_THRESHOLD = 500
            self.MIN_TIME_STEPS = 0.5

    def set_logging(self, value):
        self.logging = value

    #set height, will affect the distance
    def set_height(self, height_interval):
        if height_interval == 0:
            self.STEP_LENGTH = 0.59
        elif height_interval == 1:
            self.STEP_LENGTH = 0.64
        elif height_interval == 2:
            self.STEP_LENGTH = 0.71
        elif height_interval == 3:
            self.STEP_LENGTH = 0.77
        elif height_interval == 4:
            self.STEP_LENGTH = 0.83
        #increase step length if RUNNING
        if self.mode == 1:
            self.STEP_LENGTH *= 1.45

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
            if self.logging:
                self.file.write("%d %d %d %f\n" %(coords[0][-1], coords[1][-1], coords[2][-1], now))

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
        if self.logging:
            fname = "%d_%d_%d_%d_%d_%d" % time.localtime()[0:6]
            self.file = open(self.LOGFILE + fname + ".txt", "w")

        while 1 and not self.stop_requested:
            last_cnt = self.start_interval()
            if self.update_function is not None:
                gobject.idle_add(self.update_function, self.counter, last_cnt)

        if self.logging:
            self.file.close()

        logger.info("Thread has finished")

    def get_distance(self, steps=None):
        if steps == None:
            steps = self.counter
        return self.STEP_LENGTH * steps;

class CustomButton(hildon.Button):
    def __init__(self, icon):
        hildon.Button.__init__(self, gtk.HILDON_SIZE_AUTO_WIDTH, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.icon = icon
        self.set_size_request(int(32*1.4), int(30*1.0))
        self.retval = self.connect("expose_event", self.expose)

    def set_icon(self, icon):
        self.icon = icon

    def expose(self, widget, event):
        self.context = widget.window.cairo_create()
        self.context.rectangle(event.area.x, event.area.y,
                            event.area.width, event.area.height)

        self.context.clip()
        rect = self.get_allocation()
        self.context.rectangle(rect.x, rect.y, rect.width, rect.height)
        self.context.set_source_rgba(1, 1, 1, 0)

        style = self.rc_get_style()
        color = style.lookup_color("DefaultBackgroundColor")
        if self.state == gtk.STATE_ACTIVE:
            style = self.rc_get_style()
            color = style.lookup_color("SelectionColor")
            self.context.set_source_rgba (color.red/65535.0, color.green/65335.0, color.blue/65535.0, 0.75);
        self.context.fill()

        #img = cairo.ImageSurface.create_from_png(self.icon)

        #self.context.set_source_surface(img)
        #self.context.set_source_surface(img, rect.width/2 - img.get_width() /2, 0)
        img = gtk.Image()
        img.set_from_file(self.icon)
        buf = img.get_pixbuf()
        buf =  buf.scale_simple(int(32 * 1.5), int(30 * 1.5), gtk.gdk.INTERP_BILINEAR)

        self.context.set_source_pixbuf(buf, rect.x+(event.area.width/2-15)-8, rect.y+1)
        self.context.scale(200,200)
        self.context.paint()

        return self.retval

class PedometerHomePlugin(hildondesktop.HomePluginItem):
    button = None

    #labels for current steps
    labels = ["timer", "count", "dist", "avgSpeed"]
    #labelsC = { "timer" : None, "count" : None, "dist" : None, "avgSpeed" : None }

    #labels for all time steps
    #labelsT = { "timer" : None, "count" : None, "dist" : None, "avgSpeed" : None }
    labelsC = {}
    labelsT = {}

    pedometer = None
    startTime = None

    totalCounter = 0
    totalTime = 0
    mode = 0
    height = 0
    unit = 0

    counter = 0
    time = 0
    aspect = 0
    logging = False

    def __init__(self):
        gtk.gdk.threads_init()
        #gobject.threads_init()
        hildondesktop.HomePluginItem.__init__(self)

        self.client = gconf.client_get_default()
        try:
            self.totalCounter = self.client.get_int(COUNTER)
            self.totalTime = self.client.get_int(TIMER)
            self.mode = self.client.get_int(MODE)
            self.height = self.client.get_int(HEIGHT)
            self.unit = self.client.get_int(UNIT)
            self.aspect = self.client.get_int(ASPECT)
            self.logging = self.client.get_bool(LOGGING)
        except:
            self.client.set_int(COUNTER, 0)
            self.client.set_int(TIMER, 0)
            self.client.set_int(MODE, 0)
            self.client.set_int(HEIGHT, 0)
            self.client.set_int(UNIT, 0)
            self.client.set_int(ASPECT, 0)
            self.client.set_bool(LOGGING, False)

        self.pedometer = PedoCounter(self.update_values)
        self.pedometer.set_mode(self.mode)
        self.pedometer.set_height(self.height)

        #self.button = gtk.Button("Start")
        self.button = CustomButton(ICONSPATH + "play.png")
        self.button.connect("clicked", self.button_clicked)

        self.create_labels(self.labelsC)
        self.create_labels(self.labelsT)

        self.update_ui_values(self.labelsC, 0, 0)
        self.update_ui_values(self.labelsT, self.totalTime, self.totalCounter)

        mainHBox = gtk.HBox(spacing=1)

        descVBox = gtk.VBox(spacing=1)
        descVBox.add(self.new_label_heading())
        descVBox.add(self.new_label_heading("Time:"))
        descVBox.add(self.new_label_heading("Steps:"))
        descVBox.add(self.new_label_heading("Distance:"))
        descVBox.add(self.new_label_heading("Avg Speed:"))

        currentVBox = gtk.VBox(spacing=1)
        currentVBox.add(self.new_label_heading("Current"))
        currentVBox.add(self.labelsC["timer"])
        currentVBox.add(self.labelsC["count"])
        currentVBox.add(self.labelsC["dist"])
        currentVBox.add(self.labelsC["avgSpeed"])
        self.currentBox = currentVBox

        totalVBox = gtk.VBox(spacing=1)
        totalVBox.add(self.new_label_heading("Total"))
        totalVBox.add(self.labelsT["timer"])
        totalVBox.add(self.labelsT["count"])
        totalVBox.add(self.labelsT["dist"])
        totalVBox.add(self.labelsT["avgSpeed"])
        self.totalBox = totalVBox

        buttonVBox = gtk.VBox(spacing=1)
        buttonVBox.add(self.new_label_heading(""))
        buttonVBox.add(self.button)
        buttonVBox.add(self.new_label_heading(""))

        mainHBox.add(buttonVBox)
        mainHBox.add(descVBox)
        mainHBox.add(currentVBox)
        mainHBox.add(totalVBox)

        self.mainhbox = mainHBox

        mainHBox.show_all()
        self.add(mainHBox)
        self.update_aspect()

        self.connect("unrealize", self.close_requested)
        self.set_settings(True)
        self.connect("show-settings", self.show_settings)

    def new_label_heading(self, title=""):
        l = gtk.Label(title)
        hildon.hildon_helper_set_logical_font(l, "SmallSystemFont")
        return l

    def create_labels(self, new_labels):
        for label in self.labels:
            l = gtk.Label()
            hildon.hildon_helper_set_logical_font(l, "SmallSystemFont")
            hildon.hildon_helper_set_logical_color(l, gtk.RC_FG, gtk.STATE_NORMAL, "ActiveTextColor")
            new_labels[label] = l

    def update_aspect(self):
        if self.aspect == 0:
            self.currentBox.show_all()
            self.totalBox.show_all()
        elif self.aspect == 1:
            self.currentBox.show_all()
            self.totalBox.hide_all()
        else:
            self.currentBox.hide_all()
            self.totalBox.show_all()

    def update_ui_values(self, labels, timer, steps):
        def get_str_distance(meters):
            if meters > 1000:
                if self.unit == 0:
                    return "%.2f km" % (meters/1000)
                else:
                    return "%.2f mi" % (meters/1609.344)
            else:
                if self.unit == 0:
                    return "%d m" % meters
                else:
                    return "%d ft" % int(meters*3.2808)

        def get_avg_speed(timer, dist):
            suffix = ""
            conv = 0
            if self.unit:
                suffix = "mi/h"
                conv = 2.23693629
            else:
                suffix = "km/h"
                conv = 3.6

            if timer == 0:
                return "N/A " + suffix
            speed = 1.0 *dist / timer
            #convert from meters per second to km/h or mi/h
            speed *= conv
            return "%.2f %s" % (speed, suffix)

        tdelta = timer
        hours = int(tdelta / 3600)
        tdelta -= 3600 * hours
        mins = int(tdelta / 60)
        tdelta -= 60 * mins
        secs = int(tdelta)

        strtime = "%.2d:%.2d:%.2d" % ( hours, mins, secs)

        labels["timer"].set_label(strtime)
        labels["count"].set_label(str(steps))

        dist = self.pedometer.get_distance(steps)

        labels["dist"].set_label(get_str_distance(dist))
        labels["avgSpeed"].set_label(get_avg_speed(timer, dist))

    def update_current(self):
        self.update_ui_values(self.labelsC, self.time, self.counter)

    def update_total(self):
        self.update_ui_values(self.labelsT, self.totalTime, self.totalCounter)

    def show_settings(self, widget):
        def reset_total_counter(arg):
            widget.totalCounter = 0
            widget.totalTime = 0
            widget.update_total()
            hildon.hildon_banner_show_information(self,"None", "Total counter was resetted")

        def selector_changed(selector, data):
            widget.mode = selector.get_active(0)
            widget.client.set_int(MODE, widget.mode)
            widget.pedometer.set_mode(widget.mode)
            widget.pedometer.set_height(widget.height)
            widget.update_current()
            widget.update_total()

        def selectorH_changed(selector, data):
            widget.height = selectorH.get_active(0)
            widget.client.set_int(HEIGHT, widget.height)
            widget.pedometer.set_height(widget.height)
            widget.update_current()
            widget.update_total()


        def selectorUnit_changed(selector, data):
            widget.unit = selectorUnit.get_active(0)
            widget.client.set_int(UNIT, widget.unit)
            widget.update_current()
            widget.update_total()

        def selectorUI_changed(selector, data):
            widget.aspect = selectorUI.get_active(0)
            widget.client.set_int(ASPECT, widget.aspect)
            widget.update_aspect()

        def logButton_changed(checkButton):
            widget.logging = checkButton.get_active()
            widget.client.set_bool(LOGGING, widget.logging)

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

        selectorUnit = hildon.TouchSelector(text=True)
        selectorUnit.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorUnit.append_text("Metric (km)")
        selectorUnit.append_text("English (mi)")
        selectorUnit.connect("changed", selectorUnit_changed)

        unitPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        unitPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        unitPicker.set_title("Units")
        unitPicker.set_selector(selectorUnit)
        unitPicker.set_active(widget.unit)

        selectorUI = hildon.TouchSelector(text=True)
        selectorUI = hildon.TouchSelector(text=True)
        selectorUI.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorUI.append_text("Show current + total")
        selectorUI.append_text("Show only current")
        selectorUI.append_text("Show only total")
        selectorUI.connect("changed", selectorUI_changed)

        UIPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        UIPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        UIPicker.set_title("Widget aspect")
        UIPicker.set_selector(selectorUI)
        UIPicker.set_active(widget.aspect)

        logButton = hildon.CheckButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT)
        logButton.set_label("Log data")
        logButton.set_active(widget.logging)
        logButton.connect("toggled", logButton_changed)

        pan_area = hildon.PannableArea()
        vbox = gtk.VBox()
        vbox.add(button)
        vbox.add(modePicker)
        vbox.add(heightPicker)
        vbox.add(unitPicker)
        vbox.add(UIPicker)
        vbox.add(logButton)

        pan_area.add_with_viewport(vbox)
        pan_area.set_size_request(-1, 600)
        dialog.vbox.add(pan_area)
        dialog.show_all()
        response = dialog.run()
        #hildon.hildon_banner_show_information(self, "None", "You have to Stop/Start the counter to apply the new settings")
        dialog.destroy()

    def close_requested(self, widget):
        if self.pedometer is None:
            return

        self.pedometer.request_stop()
        if self.pedometer.isAlive():
            self.pedometer.join()

    def update_values(self, totalCurent, lastInterval):
        self.totalCounter += lastInterval
        self.counter = totalCurent

        tdelta = time.time() - self.time - self.startTime
        self.time += tdelta
        self.totalTime += tdelta

        self.update_current()
        self.update_total()

    def button_clicked(self, button):
        if self.pedometer is not None and self.pedometer.isAlive():
            #counter is running
            self.pedometer.request_stop()
            self.pedometer.join()
            self.client.set_int(COUNTER, self.totalCounter)
            self.client.set_int(TIMER, int(self.totalTime))
            #self.button.set_label("Start")
            self.button.set_icon(ICONSPATH + "play.png")
        else:
            self.pedometer = PedoCounter(self.update_values)
            self.pedometer.set_mode(self.mode)
            self.pedometer.set_height(self.height)
            self.pedometer.set_logging(self.logging)

            self.time = 0
            self.counter = 0

            self.update_current()

            self.pedometer.start()
            self.startTime = time.time()
            #self.button.set_label("Stop")
            self.button.set_icon(ICONSPATH + "stop.png")

    def do_expose_event(self, event):
        cr = self.window.cairo_create()
        cr.region(event.window.get_clip_region())
        cr.clip()
        #cr.set_source_rgba(0.4, 0.64, 0.564, 0.5)
        style = self.rc_get_style()
        color = style.lookup_color("DefaultBackgroundColor")
        cr.set_source_rgba (color.red/65535.0, color.green/65335.0, color.blue/65535.0, 0.75);

        radius = 5
        width = self.allocation.width
        height = self.allocation.height

        x = self.allocation.x
        y = self.allocation.y

        cr.move_to(x+radius, y)
        cr.line_to(x + width - radius, y)
        cr.curve_to(x + width - radius, y, x + width, y, x + width, y + radius)
        cr.line_to(x + width, y + height - radius)
        cr.curve_to(x + width, y + height - radius, x + width, y + height, x + width - radius, y + height)
        cr.line_to(x + radius, y + height)
        cr.curve_to(x + radius, y + height, x, y + height, x, y + height - radius)
        cr.line_to(x, y + radius)
        cr.curve_to(x, y + radius, x, y, x + radius, y)

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.fill_preserve()

        color = style.lookup_color("ActiveTextColor")
        cr.set_source_rgba (color.red/65535.0, color.green/65335.0, color.blue/65535.0, 0.5);
        cr.set_line_width(1)
        cr.stroke()

        hildondesktop.HomePluginItem.do_expose_event(self, event)

    def do_realize(self):
        screen = self.get_screen()
        self.set_colormap(screen.get_rgba_colormap())
        self.set_app_paintable(True)
        hildondesktop.HomePluginItem.do_realize(self)

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

