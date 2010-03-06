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

import os
import time
import pickle
from datetime import date, timedelta
from xml.dom.minidom import getDOMImplementation, parseString

import gobject
import gconf
import gtk
import cairo

import pygst
pygst.require("0.10")
import gst

import hildondesktop
import hildon

PATH = "/apps/pedometerhomewidget"
MODE = PATH + "/mode"
HEIGHT = PATH + "/height"
STEP_LENGTH = PATH + "/step_length"
WEIGHT = PATH + "/weight"
UNIT = PATH + "/unit"
SENSITIVITY = PATH + "/sensitivity"
ASPECT = PATH + "/aspect"
SECONDVIEW = PATH + "/secondview"
GRAPHVIEW = PATH + "/graphview"
NOIDLETIME = PATH + "/noidletime"
LOGGING = PATH + "/logging"

ALARM_PATH = PATH + "/alarm"
ALARM_ENABLE = ALARM_PATH + "/enable"
ALARM_FNAME = ALARM_PATH + "/fname"
ALARM_TYPE = ALARM_PATH + "/type"
ALARM_INTERVAL = ALARM_PATH + "/interval"

ICONSPATH = "/opt/pedometerhomewidget/"

unit = 0

class Singleton(object):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

class PedoIntervalCounter(Singleton):
    MIN_THRESHOLD = 500
    MIN_TIME_STEPS = 0.5
    sensitivity = 100
    mode = 0
    x = []
    y = []
    z = []
    t = []

    #TODO: check if last detected step is at the end of the interval

    def set_vals(self, coords, tval):
        self.x = coords[0]
        self.y = coords[1]
        self.z = coords[2]
        self.t = tval

    def set_mode(self, mode):
        #runnig, higher threshold to prevent fake steps
        self.mode = mode
        if mode == 1:
            self.MIN_THRESHOLD = 650.0 * (200 - self.sensitivity) / 100
            self.MIN_TIME_STEPS = 0.35
        #walking
        else:
            self.MIN_THRESHOLD = 500.0 * (200 - self.sensitivity) / 100
            self.MIN_TIME_STEPS = 0.5

    def set_sensitivity(self, value):
        self.sensitivity = value
        self.set_mode(self.mode)

    def calc_mean(self, vals):
        sum = 0
        for i in vals:
            sum += i
        if len(vals) > 0:
            return sum / len(vals)
        return 0

    def calc_stdev(self, vals):
        rez = 0
        mean = self.calc_mean(vals)
        for i in vals:
            rez += pow(abs(mean - i), 2)
        return math.sqrt(rez / len(vals))

    def calc_threshold(self, vals):
        vmax = max(vals)
        vmin = min(vals)
        mean = self.calc_mean(vals)
        threshold = max (abs(mean - vmax), abs(mean - vmin))
        return threshold

    def count_steps(self, vals, t):
        threshold = self.MIN_THRESHOLD
        mean = self.calc_mean(vals)
        cnt = 0
        i = 0
        while i < len(vals):
            if abs(vals[i] - mean) > threshold:
                cnt += 1
                ntime = t[i] + self.MIN_TIME_STEPS
                while i < len(vals) and t[i] < ntime:
                    i += 1
            i += 1
        return cnt

    def get_best_values(self, x, y, z):
        dev1 = self.calc_stdev(x)
        dev2 = self.calc_stdev(y)
        dev3 = self.calc_stdev(z)
        dev_max = max(dev1, dev2, dev3)

        if (abs(dev1 - dev_max) < 0.001):
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

class PedoValues():
    def __init__(self, time=0, steps=0, dist=0, calories=0):
        self.time = time
        self.steps = steps
        self.calories = calories
        self.dist = dist

    def __add__(self, other):
        return PedoValues(self.time + other.time,
                          self.steps + other.steps,
                          self.dist + other.dist,
                          self.calories + other.calories)

    def __sub__(self, other):
        return PedoValues(self.time - other.time,
                          self.steps - other.steps,
                          self.dist - other.dist,
                          self.calories - other.calories)

    def get_print_time(self):
        tdelta = self.time
        hours = int(tdelta / 3600)
        tdelta -= 3600 * hours
        mins = int(tdelta / 60)
        tdelta -= 60 * mins
        secs = int(tdelta)
        strtime = "%.2d:%.2d:%.2d" % (hours, mins, secs)
        return strtime

    def get_print_distance(self):
        global unit
        if self.dist > 1000:
            if unit == 0:
                return "%.2f km" % (self.dist / 1000)
            else:
                return "%.2f mi" % (self.dist / 1609.344)
        else:
            if unit == 0:
                return "%d m" % self.dist
            else:
                return "%d ft" % int(self.dist * 3.2808)

    def get_avg_speed(self):
        global unit
        conv = 0
        if unit:
            conv = 2.23693629
        else:
            conv = 3.6

        if self.time == 0:
            return 0
        speed = 1.0 * self.dist / self.time
        return speed * conv

    def get_print_avg_speed(self):
        global unit
        suffix = ""
        conv = 0
        if unit:
            suffix = "mi/h"
            conv = 2.23693629
        else:
            suffix = "km/h"
            conv = 3.6

        if self.time == 0:
            return "N/A " + suffix
        speed = 1.0 * self.dist / self.time
        #convert from meters per second to km/h or mi/h
        speed *= conv
        return "%.2f %s" % (speed, suffix)

    def get_print_steps(self):
        return str(self.steps)

    def get_print_calories(self):
        return "%.2f" % self.calories

class PedoRepository(Singleton):
    values = {}

    def load(self):
        raise NotImplementedError("Must be implemented by subclass")

    def save(self):
        raise NotImplementedError("Must be implemented by subclass")

    def reset_values(self):
        self.values = {}
        self.save()

    def get_history_count(self):
        """return the number of days in the log"""
        return len(values)

    def get_values(self):
        return self.values

    def add_values(self, values, when=None):
        if when is None:
            when = date.today()
        """add PedoValues values to repository """
        try:
            self.values[when] = self.values[when] + values
        except KeyError:
            self.values[when] = values

    def get_last_7_days(self):
        ret = []
        day = date.today()
        for i in range(7):
            try:
                ret.append(self.values[day])
            except KeyError:
                ret.append(PedoValues())
            day = day - timedelta(days=1)
        return ret

    def get_last_weeks(self):
        delta = timedelta(days=1)
        day = date.today()
        week = int(date.today().strftime("%W"))
        val = PedoValues()
        ret = []
        for i in range(56):
            try:
                val += self.values[day]
            except KeyError:
                pass
            w = int(day.strftime("%W"))
            if w != week:
                ret.append(val)
                val = PedoValues()
                week = w
                if len(ret) == 7:
                    break
            day -= delta
        return ret

    def get_alltime_values(self):
        ret = PedoValues()
        for k, v in self.values.iteritems():
            ret = ret + v
        return ret

    def get_today_values(self):
        try:
            return self.values[date.today()]
        except KeyError:
            return PedoValues()

    def get_this_week_values(self):
        day = date.today()
        ret = PedoValues()
        while True:
            try:
                ret += self.values[day]
            except:
                pass
            if day.weekday() == 0:
                break
            day = day - timedelta(days=1)

        return ret

class PedoRepositoryXML(PedoRepository):
    DIR = os.path.join(os.path.expanduser("~"), ".pedometer")
    FILE = os.path.join(DIR, "data.xml")
    FILE2 = os.path.join(DIR, "pickle.log")
    def __init__(self):
        if not os.path.exists(self.DIR):
            os.makedirs(self.DIR)
        PedoRepository.__init__(self)

    def load(self):
        try:
            f = open(self.FILE, "r")
            dom = parseString(f.read())
            values = dom.getElementsByTagName("pedometer")[0]
            for v in values.getElementsByTagName("date"):
                d = int(v.getAttribute("ordinal_day"))
                steps = int(v.getAttribute("steps"))
                calories = float(v.getAttribute("calories"))
                dist = float(v.getAttribute("dist"))
                time = float(v.getAttribute("time"))
                day = date.fromordinal(d)
                self.values[day] = PedoValues(time, steps, dist, calories)

            f.close()
        except Exception, e:
            logger.error("Error while loading data from xml file: %s" % e)

    def save(self):
        try:
            f = open(self.FILE, "w")

            impl = getDOMImplementation()

            newdoc = impl.createDocument(None, "pedometer", None)
            top_element = newdoc.documentElement
            for k, v in self.values.iteritems():
                d = newdoc.createElement('date')
                d.setAttribute("day", str(k.isoformat()))
                d.setAttribute("ordinal_day", str(k.toordinal()))
                d.setAttribute("steps", str(v.steps))
                d.setAttribute("time", str(v.time))
                d.setAttribute("dist", str(v.dist))
                d.setAttribute("calories", str(v.calories))
                top_element.appendChild(d)

            newdoc.appendChild(top_element)
            newdoc.writexml(f)
            #f.write(newdoc.toprettyxml())
            f.close()
        except Exception, e:
            logger.error("Error while saving data to xml file: %s" % e)

class PedoRepositoryPickle(PedoRepository):
    DIR = os.path.join(os.path.expanduser("~"), ".pedometer")
    FILE = os.path.join(DIR, "pickle.log")

    def __init__(self):
        if not os.path.exists(self.DIR):
            os.makedirs(self.DIR)
        PedoRepository.__init__(self)

    def load(self):
        try:
            f = open(self.FILE, "rb")
            self.values = pickle.load(f)
            f.close()
        except Exception, e:
            logger.error("Error while loading pickle file: %s" % e)

    def save(self):
        try:
            f = open(self.FILE, "wb")
            pickle.dump(self.values, f)
            f.close()
        except Exception, e:
            logger.error("Error while saving data to pickle: %s" % e)

class PedoController(Singleton):
    mode = 0
    unit = 0
    height_interval = 0
    #what to display in second view - 0 - alltime, 1 - today, 2 - week
    second_view = 0
    callback_update_ui = None
    no_idle_time = False

    STEP_LENGTH = 0.7
    #values for the two views in the widget ( current and day/week/alltime)
    v = [PedoValues(), PedoValues()]

    last_time = 0
    is_running = False

    observers = []

    midnight_set = False
    midnight_source_id = None

    def __init__(self):
        self.pedometer = PedoCounter(self.steps_detected)
        self.pedometerInterval = PedoIntervalCounter()
        self.pedometerInterval.set_mode(self.mode)
        self.repository = PedoRepositoryXML()
        self.repository.load()

        self.load_values()

        if not self.midnight_set:
            self.update_at_midnight()
            self.midnight_set = True

    def update_at_midnight(self):
        next_day = date.today() + timedelta(days=1)
        diff = time.mktime(next_day.timetuple()) - time.time()
        diff = int(diff+5)
        self.midnight_source_id = gobject.timeout_add_seconds(diff, self.midnight_callback, True)

    def stop_midnight_callback(self):
        if self.midnight_source_id is not None:
            gobject.source_remove(self.midnight_source_id)

    def midnight_callback(self, first=False):
        self.load_values()
        self.notify()
        if first:
            self.midnight_source_id = gobject.timeout_add_seconds(24*3600, self.midnight_callback)
            return False
        else:
            return True

    def load_values(self):
        if self.second_view == 0:
            self.v[1] = self.repository.get_alltime_values()
        elif self.second_view == 1:
            self.v[1] = self.repository.get_today_values()
        else:
            self.v[1] = self.repository.get_this_week_values()

    def save_values(self):
        self.repository.add_values(self.v[0])
        self.repository.save()
        self.load_values()

    def start_pedometer(self):
        self.v[0] = PedoValues()
        self.last_time = time.time()
        self.is_running = True
        self.pedometer.start()
        self.notify(True)

    def reset_all_values(self):
        self.repository.reset_values()
        self.v[0] = PedoValues()
        self.v[1] = PedoValues()
        self.notify()

    def stop_pedometer(self):
        self.is_running = False
        self.pedometer.request_stop()

    def get_first(self):
        return self.v[0]

    def get_second(self):
        if self.is_running:
            return self.v[0] + self.v[1]
        else:
            return self.v[1]

    def update_current(self):
        """
        Update distance and calories for current values based on new height, mode values
        """
        self.v[0].dist = self.get_distance(self.v[0].steps)
        self.v[0].calories = self.get_calories(self.v[0].steps)

    def steps_detected(self, cnt, last_steps=False):
        if not last_steps and cnt == 0 and self.no_idle_time:
            logger.info("No steps detected, timer is paused")
        else:
            self.v[0].steps += cnt
            self.v[0].dist += self.get_distance(cnt)
            self.v[0].calories += self.get_calories(self.get_distance(cnt))
            self.v[0].time += time.time() - self.last_time
            if last_steps:
                self.save_values()
                self.notify()
            else:
                self.notify(True)
        self.last_time = time.time()

    def get_calories(self, distance):
        """calculate lost calories for the distance and weight given as parameters
        """
        #different coefficient for running and walking
        if self.mode == 0:
            coef = 0.53
        else:
            coef = 0.75

        #convert distance from meters to miles
        distance *= 0.000621371192

        weight = self.weight
        #convert weight from kg to pounds
        if self.unit == 0:
            weight *= 2.20462262
        return weight * distance * coef

    def set_mode(self, mode):
        self.mode = mode
        self.set_height(self.height_interval)
        self.pedometerInterval.set_mode(self.mode)
        self.notify()

    def set_unit(self, new_unit):
        self.unit = new_unit
        global unit
        unit = new_unit
        self.notify()

    def get_str_weight_unit(self):
        if self.unit == 0:
            return "kg"
        else:
            return "lb"

    def set_weight(self, value):
        self.weight = value
        self.notify()

    def get_weight(self):
        return self.weight

    def set_sensitivity(self, value):
        self.sensitivity = value
        self.pedometerInterval.set_sensitivity(value)

    def get_sensitivity(self):
        return self.sensitivity

    def set_second_view(self, second_view):
        self.second_view = second_view
        self.load_values()
        self.notify()

    def set_callback_ui(self, func):
        self.callback_update_ui = func

    def set_height(self, height_interval, step_length=None):
        self.height_interval = height_interval
        if step_length is None:
            step_length = self.STEP_LENGTH
        #set height, will affect the distance
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
        elif height_interval == 5:
            self.STEP_LENGTH = step_length
        #increase step length if RUNNING
        if self.mode == 1:
            self.STEP_LENGTH *= 1.45
        self.notify()

    def set_no_idle_time(self, value):
        self.no_idle_time = value

    def get_distance(self, steps=None):
        if steps == None:
            steps = self.counter
        return self.STEP_LENGTH * steps;

    def add_observer(self, func):
        try:
            self.observers.index(func)
        except:
            self.observers.append(func)

    def remove_observer(self, func):
        self.observers.remove(func)

    def notify(self, optional=False):
        if self.callback_update_ui is not None:
            self.callback_update_ui()

        for func in self.observers:
            func(optional)

class AlarmController(Singleton):
    enable = False
    fname = "/home/user/MyDocs/.sounds/Ringtones/Bicycle.aac"
    interval = 5
    type = 0

    player = None
    is_playing = False
    pedo_controller = None

    def __init__(self):
        self.client = gconf.client_get_default()

        self.enable = self.client.get_bool(ALARM_ENABLE)
        self.fname = self.client.get_string(ALARM_FNAME)
        self.interval = self.client.get_int(ALARM_INTERVAL)
        self.type = self.client.get_int(ALARM_TYPE)

        self.pedo_controller = PedoController()
        if self.enable:
            self.init_player()
            self.pedo_controller.add_observer(self.update)
            self.start_value = self.pedo_controller.get_first()

    def init_player(self):
        self.player = gst.element_factory_make("playbin2", "player")
        fakesink = gst.element_factory_make("fakesink", "fakesink")
        self.player.set_property("video-sink", fakesink)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.is_playing = False
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            self.is_playing = False
            err, debug = message.parse_error()
            logger.error("ERROR: %s, %s" % (err, debug) )

    def update(self, optional):
        diff = self.pedo_controller.get_first() - self.start_value
        if self.type == 0 and diff.time >= self.interval * 60 or \
                   self.type == 1 and diff.steps >= self.interval or \
                   self.type == 2 and diff.dist >= self.interval or \
                   self.type == 3 and diff.calories >= self.interval:
            self.play()
            #get new instance of current values
            self.start_value = PedoValues() + self.pedo_controller.get_first()
            logger.info("Alarm!")

    def play(self):
        if self.player is None:
            self.init_player()
        if self.is_playing:
            self.player.set_state(gst.STATE_NULL)
            self.is_playing = False
        else:
            self.player.set_property("uri", "file://" + self.fname)
            self.player.set_state(gst.STATE_PLAYING)
            self.is_playing = True

    def stop(self):
        self.player.set_state(gst.STATE_NULL)

    def set_enable(self, value):
       self.enable = value
       self.client.set_bool(ALARM_ENABLE, value)
       if self.enable:
           self.init_player()
           self.pedo_controller.add_observer(self.update)
           self.start_value = self.pedo_controller.get_first()
       else:
           self.stop()
           self.player = None
           self.pedo_controller.remove_observer(self.update)

    def get_enable(self):
        return self.enable

    def set_alarm_file(self, fname):
        self.fname = fname
        self.client.set_string(ALARM_FNAME, fname)

    def get_alarm_file(self):
        if self.fname == None:
            return ""
        return self.fname

    def set_interval(self, interval):
        self.interval = interval
        self.client.set_int(ALARM_INTERVAL, interval)

    def get_interval(self):
        return self.interval

    def set_type(self, type):
        self.type = type
        self.client.set_int(ALARM_TYPE, type)

    def get_type(self):
        return self.type

class PedoCounter(Singleton):
    COORD_FNAME = "/sys/class/i2c-adapter/i2c-3/3-001d/coord"
    COORD_FNAME_SDK = "/home/andrei/pedometer-widget-0.1/date.txt"
    LOGFILE = "/home/user/log_pedometer"
    #time in ms between two accelerometer data reads
    COORD_GET_INTERVAL = 25

    COUNT_INTERVAL = 5

    interval_counter = None
    stop_requested = False
    update_function = None
    logging = False
    isRunning = False

    def __init__(self, update_function=None):
        if not os.path.exists(self.COORD_FNAME):
            self.COORD_FNAME = self.COORD_FNAME_SDK

        self.interval_counter = PedoIntervalCounter()
        self.update_function = update_function

    def set_logging(self, value):
        self.logging = value

    def get_rotation(self):
        f = open(self.COORD_FNAME, 'r')
        coords = [int(w) for w in f.readline().split()]
        f.close()
        return coords

    def start(self):
        logger.info("Counter started")
        self.isRunning = True
        self.stop_requested = False
        if self.logging:
            fname = "%d_%d_%d_%d_%d_%d" % time.localtime()[0:6]
            self.file = open(self.LOGFILE + fname + ".txt", "w")
        gobject.idle_add(self.run)

    def run(self):
        self.coords = [[], [], []]
        self.stime = time.time()
        self.t = []
        gobject.timeout_add(self.COORD_GET_INTERVAL, self.read_coords)
        return False

    def read_coords(self):
        x, y, z = self.get_rotation()
        self.coords[0].append(int(x))
        self.coords[1].append(int(y))
        self.coords[2].append(int(z))
        now = time.time() - self.stime
        if self.logging:
            self.file.write("%d %d %d %f\n" % (self.coords[0][-1], self.coords[1][-1], self.coords[2][-1], now))

        self.t.append(now)
        #call stop_interval
        ret = True
        if self.t[-1] > self.COUNT_INTERVAL or self.stop_requested:
            ret = False
            gobject.idle_add(self.stop_interval)
        return ret

    def stop_interval(self):
        self.interval_counter.set_vals(self.coords, self.t)
        cnt = self.interval_counter.number_steps()

        logger.info("Number of steps detected for last interval %d, number of coords: %d" % (cnt, len(self.t)))

        gobject.idle_add(self.update_function, cnt, self.stop_requested)

        if self.stop_requested:
            gobject.idle_add(self.stop)
        else:
            gobject.idle_add(self.run)
        return False

    def stop(self):
        if self.logging:
            self.file.close()
        logger.info("Counter has finished")

    def request_stop(self):
        self.stop_requested = True
        self.isRunning = False

class CustomButton(hildon.Button):
    def __init__(self, icon):
        hildon.Button.__init__(self, gtk.HILDON_SIZE_AUTO_WIDTH, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.icon = icon
        self.set_size_request(int(32 * 1.4), int(30 * 1.0))
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
            self.context.set_source_rgba (color.red / 65535.0, color.green / 65335.0, color.blue / 65535.0, 0.75);
        self.context.fill()

        #img = cairo.ImageSurface.create_from_png(self.icon)

        #self.context.set_source_surface(img)
        #self.context.set_source_surface(img, rect.width/2 - img.get_width() /2, 0)
        img = gtk.Image()
        img.set_from_file(self.icon)
        buf = img.get_pixbuf()
        buf = buf.scale_simple(int(32 * 1.5), int(30 * 1.5), gtk.gdk.INTERP_BILINEAR)

        self.context.set_source_pixbuf(buf, rect.x + (event.area.width / 2 - 15) - 8, rect.y + 1)
        self.context.scale(200, 200)
        self.context.paint()

        return self.retval

class CustomEventBox(gtk.EventBox):

    def __init__(self):
        gtk.EventBox.__init__(self)

    def do_expose_event(self, event):
        self.context = self.window.cairo_create()
        self.context.rectangle(event.area.x, event.area.y,
                            event.area.width, event.area.height)

        self.context.clip()
        rect = self.get_allocation()
        self.context.rectangle(rect.x, rect.y, rect.width, rect.height)

        if self.state == gtk.STATE_ACTIVE:
            style = self.rc_get_style()
            color = style.lookup_color("SelectionColor")
            self.context.set_source_rgba (color.red / 65535.0, color.green / 65335.0, color.blue / 65535.0, 0.75);
        else:
            self.context.set_source_rgba(1, 1, 1, 0)
        self.context.fill()

        gtk.EventBox.do_expose_event(self, event)

class GraphController(Singleton):
    ytitles = ["Steps", "Average Speed", "Distance", "Calories"]
    xtitles = ["Day", "Week"] # "Today"]
    widget = None
    def __init__(self):
        self.repository = PedoRepositoryXML()
        self.last_update = 0
        PedoController().add_observer(self.update_ui)

    def set_graph(self, widget):
        self.widget = widget
        self.update_ui()

    def set_current_view(self, view):
        """
        current_view % len(ytitles) - gives the ytitle
        current_view / len(ytitles) - gives the xtitle
        """
        self.current_view = view

        if self.current_view == len(self.ytitles) * len(self.xtitles):
            self.current_view = 0
        self.x_id = self.current_view / len(self.ytitles)
        self.y_id = self.current_view % len(self.ytitles)

    def next_view(self):
        self.set_current_view(self.current_view+1)
        self.update_ui()
        return self.current_view

    def last_weeks_labels(self):
        d = date.today()
        delta = timedelta(days=7)
        ret = []
        for i in range(7):
            ret.append(d.strftime("Week %W"))
            d = d - delta
        return ret

    def compute_values(self):
        labels = []
        if self.x_id == 0:
            values = self.repository.get_last_7_days()
            d = date.today()
            delta = timedelta(days=1)
            for i in range(7):
                labels.append(d.ctime().split()[0])
                d = d - delta

        elif self.x_id == 1:
            values = self.repository.get_last_weeks()
            d = date.today()
            for i in range(7):
                labels.append(d.strftime("Week %W"))
                d = d - timedelta(days=7)
        else:
            values = self.repository.get_today()
            #TODO get labels

        if self.y_id == 0:
            yvalues = [line.steps for line in values]
        elif self.y_id == 1:
            yvalues = [line.get_avg_speed() for line in values]
        elif self.y_id == 2:
            yvalues = [line.dist for line in values]
        else:
            yvalues = [line.calories for line in values]

        #determine values for y lines in graph
        diff = self.get_best_interval_value(max(yvalues))
        ytext = []
        for i in range(6):
            ytext.append(str(int(i*diff)))

        if self.widget is not None:
            yvalues.reverse()
            labels.reverse()
            self.widget.values = yvalues
            self.widget.ytext = ytext
            self.widget.xtext = labels
            self.widget.max_value = diff * 5
            self.widget.text = self.xtitles[self.x_id] + " / " + self.ytitles[self.y_id]
            self.widget.queue_draw()
        else:
            logger.error("Widget not set in GraphController")

    def get_best_interval_value(self, max_value):
        diff =  1.0 * max_value / 5
        l = len(str(int(diff)))
        d = math.pow(10, l/2)
        val = int(math.ceil(1.0 * diff / d)) * d
        if val == 0:
            val = 1
        return val

    def update_ui(self, optional=False):
        """update graph values every x seconds"""
        if optional and self.last_update - time.time() < 600:
            return
        if self.widget is None:
            return

        self.compute_values()
        self.last_update = time.time()

class GraphWidget(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.set_size_request(-1, 150)
        self.yvalues = 5

        """sample values"""
        self.ytext = ["   0", "1000", "2000", "3000", "4000", "5000"]
        self.xtext = ["Monday", "Tuesday", "Wednesday","Thursday", "Friday", "Saturday", "Sunday"]
        self.values = [1500, 3400, 4000, 3600, 3200, 0, 4500]
        self.max_value = 5000
        self.text = "All time steps"

    def do_expose_event(self, event):
        context = self.window.cairo_create()

        # set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y,
                               event.area.width, event.area.height)
        context.clip()

        context.save()

        context.set_operator(cairo.OPERATOR_SOURCE)
        style = self.rc_get_style()

        if self.state == gtk.STATE_ACTIVE:
            color = style.lookup_color("SelectionColor")
        else:
             color = style.lookup_color("DefaultBackgroundColor")
        context.set_source_rgba (color.red / 65535.0, color.green / 65335.0, color.blue / 65535.0, 0.75)

        context.paint()
        context.restore();
        self.draw(context)

    def draw(self, cr):
        space_below = 20
        space_above = 10
        border_right = 10
        border_left = 30

        rect = self.get_allocation()
        x = rect.width
        y = rect.height

        cr.select_font_face("Purisa", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(13)

        #check space needed to display ylabels
        te = cr.text_extents(self.ytext[-1])
        border_left = te[2] + 7

        cr.set_source_rgb(1, 1, 1)
        cr.move_to(border_left, space_above)
        cr.line_to(border_left, y-space_below)
        cr.set_line_width(2)
        cr.stroke()

        cr.move_to(border_left, y-space_below)
        cr.line_to(x-border_right, y-space_below)
        cr.set_line_width(2)
        cr.stroke()

        ydiff = (y-space_above-space_below) / self.yvalues
        for i in range(self.yvalues):
            yy = y-space_below-ydiff*(i+1)
            cr.move_to(border_left, yy)
            cr.line_to(x-border_right, yy)
            cr.set_line_width(0.8)
            cr.stroke()


        for i in range(6):
            yy = y - space_below - ydiff*i + 5
            te = cr.text_extents(self.ytext[i])

            cr.move_to(border_left-te[2]-2, yy)
            cr.show_text(self.ytext[i])

        cr.set_font_size(15)
        te = cr.text_extents(self.text)
        cr.move_to((x-te[2])/2, y-5)
        cr.show_text(self.text)

        graph_x_space = x - border_left - border_right
        graph_y_space = y - space_below - space_above
        bar_width = graph_x_space*0.75 / len(self.values)
        bar_distance = graph_x_space*0.25 / (1+len(self.values))

        #set dummy max value to avoid exceptions
        if self.max_value == 0:
            self.max_value = 100
        for i in range(len(self.values)):
            xx = border_left + (i+1)*bar_distance + i * bar_width
            yy = y-space_below
            height = graph_y_space * (1.0 * self.values[i] / self.max_value)
            cr.set_source_rgba(1, 1, 1, 0.75)
            cr.rectangle(int(xx), int(yy-height), int(bar_width), int(height))
            cr.fill()

        cr.set_source_rgba(1, 1, 1, 1)
        cr.select_font_face("Purisa", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(13)

        cr.rotate(2*math.pi * (-45) / 180)
        for i in range(len(self.values)):
            xx = y - space_below - 10
            yy = border_left + (i+1)*bar_distance + i * bar_width
            cr.move_to(-xx, yy + bar_width*1.25 / 2)
            cr.show_text(self.xtext[i])

class PedometerHomePlugin(hildondesktop.HomePluginItem):
    button = None

    #labels to display
    labels = ["timer", "count", "dist", "avgSpeed", "calories"]

    #current view
    labelsC = {}

    #second view ( day / week/ alltime)
    labelsT = {}

    second_view_labels = ["All-time", "Today", "This week"]

    controller = None
    graph_controller = None

    mode = 0
    height = 0
    weight = 70
    unit = 0
    aspect = 0
    sensitivity = 100
    second_view = 0
    graph_view = 0
    no_idle_time = False
    logging = False

    def __init__(self):
        hildondesktop.HomePluginItem.__init__(self)

        gobject.type_register(CustomEventBox)
        gobject.type_register(GraphWidget)

        self.client = gconf.client_get_default()

        self.mode = self.client.get_int(MODE)
        self.height = self.client.get_int(HEIGHT)
        self.step_length = self.client.get_float(STEP_LENGTH)
        self.weight = self.client.get_int(WEIGHT)
        self.unit = self.client.get_int(UNIT)
        self.sensitivity = self.client.get_int(SENSITIVITY)
        self.aspect = self.client.get_int(ASPECT)
        self.second_view = self.client.get_int(SECONDVIEW)
        self.graph_view = self.client.get_int(GRAPHVIEW)
        self.no_idle_time = self.client.get_bool(NOIDLETIME)
        self.logging = self.client.get_bool(LOGGING)

        self.controller = PedoController()
        self.controller.set_height(self.height, self.step_length)
        self.controller.set_weight(self.weight)
        self.controller.set_mode(self.mode)
        self.controller.set_unit(self.unit)
        self.controller.set_sensitivity(self.sensitivity)
        self.controller.set_second_view(self.second_view)
        self.controller.set_callback_ui(self.update_values)
        self.controller.set_no_idle_time(self.no_idle_time)

        self.graph_controller = GraphController()
        self.graph_controller.set_current_view(self.graph_view)

        self.alarm_controller = AlarmController()

        self.button = CustomButton(ICONSPATH + "play.png")
        self.button.connect("clicked", self.button_clicked)

        self.create_labels(self.labelsC)
        self.create_labels(self.labelsT)
        self.label_second_view = self.new_label_heading(self.second_view_labels[self.second_view])

        self.update_current()
        self.update_total()

        mainHBox = gtk.HBox(spacing=1)

        descVBox = gtk.VBox(spacing=1)
        descVBox.add(self.new_label_heading())
        descVBox.add(self.new_label_heading("Time:"))
        descVBox.add(self.new_label_heading("Steps:"))
        descVBox.add(self.new_label_heading("Calories:"))
        descVBox.add(self.new_label_heading("Distance:"))
        descVBox.add(self.new_label_heading("Avg Speed:"))

        currentVBox = gtk.VBox(spacing=1)
        currentVBox.add(self.new_label_heading("Current"))
        currentVBox.add(self.labelsC["timer"])
        currentVBox.add(self.labelsC["count"])
        currentVBox.add(self.labelsC["calories"])
        currentVBox.add(self.labelsC["dist"])
        currentVBox.add(self.labelsC["avgSpeed"])
        self.currentBox = currentVBox

        totalVBox = gtk.VBox(spacing=1)
        totalVBox.add(self.label_second_view)
        totalVBox.add(self.labelsT["timer"])
        totalVBox.add(self.labelsT["count"])
        totalVBox.add(self.labelsT["calories"])
        totalVBox.add(self.labelsT["dist"])
        totalVBox.add(self.labelsT["avgSpeed"])
        self.totalBox = totalVBox

        buttonVBox = gtk.VBox(spacing=1)
        buttonVBox.add(self.new_label_heading(""))
        buttonVBox.add(self.button)
        buttonVBox.add(self.new_label_heading(""))

        eventBox = CustomEventBox()
        eventBox.set_visible_window(False)
        eventBox.add(totalVBox)
        eventBox.connect("button-press-event", self.eventBox_clicked)
        eventBox.connect("button-release-event", self.eventBox_clicked_release)

        mainHBox.add(buttonVBox)
        mainHBox.add(descVBox)
        mainHBox.add(currentVBox)
        mainHBox.add(eventBox)
        self.mainhbox = mainHBox

        graph = GraphWidget()
        self.graph_controller.set_graph(graph)

        eventBoxGraph = CustomEventBox()
        eventBoxGraph.set_visible_window(False)
        eventBoxGraph.add(graph)
        self.graph = graph
        eventBoxGraph.connect("button-press-event", self.eventBoxGraph_clicked)
        eventBoxGraph.connect("button-release-event", self.eventBoxGraph_clicked_release)
        self.graphBox = eventBoxGraph

        self.mainvbox = gtk.VBox()

        self.mainvbox.add(mainHBox)
        self.mainvbox.add(eventBoxGraph)

        self.mainvbox.show_all()
        self.add(self.mainvbox)
        self.update_aspect()

        self.connect("unrealize", self.close_requested)
        self.set_settings(True)
        self.connect("show-settings", self.show_settings)

    def eventBoxGraph_clicked(self, widget, data=None):
        widget.set_state(gtk.STATE_ACTIVE)

    def eventBoxGraph_clicked_release(self, widget, data=None):
        self.graph_view = self.graph_controller.next_view()
        self.client.set_int(GRAPHVIEW, self.graph_view)

        widget.set_state(gtk.STATE_NORMAL)

    def eventBox_clicked(self, widget, data=None):
        widget.set_state(gtk.STATE_ACTIVE)

    def eventBox_clicked_release(self, widget, data=None):
        widget.set_state(gtk.STATE_NORMAL)

        self.second_view = (self.second_view + 1) % 3
        self.controller.set_second_view(self.second_view)
        self.client.set_int(SECONDVIEW, self.second_view)

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

        if self.aspect > 0:
            self.graphBox.hide_all()
        else:
            self.graphBox.show_all()

        if self.aspect == 0 or self.aspect == 1:
            self.currentBox.show_all()
            self.totalBox.show_all()
        elif self.aspect == 2:
            self.currentBox.show_all()
            self.totalBox.hide_all()
        else:
            self.currentBox.hide_all()
            self.totalBox.show_all()

        x,y = self.size_request()
        self.resize(x,y)

    def update_ui_values(self, labels, values):
        labels["timer"].set_label(values.get_print_time())
        labels["count"].set_label(values.get_print_steps())
        labels["dist"].set_label(values.get_print_distance())
        labels["avgSpeed"].set_label(values.get_print_avg_speed())
        labels["calories"].set_label(values.get_print_calories())

    def update_current(self):
        self.update_ui_values(self.labelsC, self.controller.get_first())

    def update_total(self):
        self.update_ui_values(self.labelsT, self.controller.get_second())

    def show_alarm_settings(self, main_button):
        def choose_file(widget):
            file = hildon.FileChooserDialog(self, gtk.FILE_CHOOSER_ACTION_OPEN, hildon.FileSystemModel() )
            file.show()
            if ( file.run() == gtk.RESPONSE_OK):
                fname = file.get_filename()
                widget.set_value(fname)
                self.alarm_controller.set_alarm_file(fname)
            file.destroy()

        def test_sound(button):
            try:
                self.alarm_controller.play()
            except Exception, e:
                logger.error("Could not play alarm sound: %s" % e)
                hildon.hildon_banner_show_information(self, "None", "Could not play alarm sound")

        def enableButton_changed(button):
            value = button.get_active()
            self.alarm_controller.set_enable(value)
            if value:
                main_button.set_value("Enabled")
            else:
                main_button.set_value("Disabled")

        def selectorType_changed(selector, data, labelEntry2):
            self.alarm_controller.set_type(selector.get_active(0))
            labelEntry2.set_label(suffix[self.alarm_controller.get_type()])

        dialog = gtk.Dialog()
        dialog.set_title("Alarm settings")
        dialog.add_button("OK", gtk.RESPONSE_OK)

        enableButton = hildon.CheckButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT)
        enableButton.set_label("Enable alarm")
        enableButton.set_active(self.alarm_controller.get_enable())
        enableButton.connect("toggled", enableButton_changed)

        testButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        testButton.set_alignment(0, 0.8, 1, 1)
        testButton.set_title("Test sound")
        testButton.connect("pressed", test_sound)

        fileButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        fileButton.set_alignment(0, 0.8, 1, 1)
        fileButton.set_title("Alarm sound")
        fileButton.set_value(self.alarm_controller.get_alarm_file())
        fileButton.connect("pressed", choose_file)

        labelEntry = gtk.Label("Notify every:")
        suffix = ["mins", "steps", "m/ft", "calories"]
        labelEntry2 = gtk.Label(suffix[self.alarm_controller.get_type()])
        intervalEntry = hildon.Entry(gtk.HILDON_SIZE_AUTO_WIDTH)
        intervalEntry.set_text(str(self.alarm_controller.get_interval()))

        selectorType = hildon.TouchSelector(text=True)
        selectorType.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorType.append_text("Time")
        selectorType.append_text("Steps")
        selectorType.append_text("Distance")
        selectorType.append_text("Calories")
        selectorType.connect("changed", selectorType_changed, labelEntry2)

        typePicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        typePicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        typePicker.set_title("Alarm type")
        typePicker.set_selector(selectorType)
        typePicker.set_active(self.alarm_controller.get_type())

        hbox = gtk.HBox()
        hbox.add(labelEntry)
        hbox.add(intervalEntry)
        hbox.add(labelEntry2)

        dialog.vbox.add(enableButton)
        dialog.vbox.add(fileButton)
        dialog.vbox.add(testButton)
        dialog.vbox.add(typePicker)
        dialog.vbox.add(hbox)
        dialog.show_all()
        while 1:
            response = dialog.run()
            if response != gtk.RESPONSE_OK:
                break
            try:
                value = int(intervalEntry.get_text())
                self.alarm_controller.set_interval(value)
                break
            except:
                hildon.hildon_banner_show_information(self, "None", "Invalid interval")

        dialog.destroy()

    def show_settings(self, widget):
        def reset_total_counter(arg):
            note = hildon.hildon_note_new_confirmation(self.dialog, "Are you sure you want to delete all your pedometer history?")
            ret = note.run()
            if ret == gtk.RESPONSE_OK:
                self.controller.reset_all_values()
                hildon.hildon_banner_show_information(self, "None", "All history was deleted")
            note.destroy()

        def alarmButton_pressed(widget):
            self.show_alarm_settings(widget)

        def selector_changed(selector, data):
            widget.mode = selector.get_active(0)
            widget.client.set_int(MODE, widget.mode)
            widget.controller.set_mode(widget.mode)

        def selectorUnit_changed(selector, data):
            widget.unit = selector.get_active(0)
            widget.client.set_int(UNIT, widget.unit)
            widget.controller.set_unit(widget.unit)

            update_weight_button()
            stepLengthButton_value_update()

        def selectorUI_changed(selector, data):
            widget.aspect = selectorUI.get_active(0)
            widget.client.set_int(ASPECT, widget.aspect)
            widget.update_aspect()

        def logButton_changed(checkButton):
            widget.logging = checkButton.get_active()
            widget.client.set_bool(LOGGING, widget.logging)

        def idleButton_changed(idleButton):
            widget.no_idle_time = idleButton.get_active()
            widget.client.set_bool(NOIDLETIME, widget.no_idle_time)
            widget.controller.set_no_idle_time(widget.no_idle_time)

        def update_weight_button():
            weightButton.set_value(str(self.controller.get_weight()) + \
                                           " " + self.controller.get_str_weight_unit() )

        def weight_dialog(button):
            dialog = gtk.Dialog("Weight", self.dialog)
            dialog.add_button("OK", gtk.RESPONSE_OK)

            label = gtk.Label("Weight:")
            entry = gtk.Entry()
            entry.set_text(str(self.controller.get_weight()))

            suffixLabel = gtk.Label(self.controller.get_str_weight_unit())

            hbox = gtk.HBox()
            hbox.add(label)
            hbox.add(entry)
            hbox.add(suffixLabel)

            dialog.vbox.add(hbox)
            dialog.show_all()
            while 1:
                response = dialog.run()
                if response != gtk.RESPONSE_OK:
                    break
                try:
                    value = int(entry.get_text())
                    if value <= 0:
                        raise ValueError
                    self.controller.set_weight(value)
                    self.client.set_int(WEIGHT, value)
                    update_weight_button()
                    break
                except:
                    hildon.hildon_banner_show_information(self, "None", "Invalid weight")
            dialog.destroy()

        def sensitivity_dialog(button):
            def seekbar_changed(seekbar):
                label.set_text(str(seekbar.get_position()) + " %")

            dialog = gtk.Dialog("Sensitivity", self.dialog)
            dialog.add_button("OK", gtk.RESPONSE_OK)
            seekbar = hildon.Seekbar()
            seekbar.set_size_request(400, -1)
            seekbar.set_total_time(200)
            seekbar.set_position(self.controller.get_sensitivity())
            seekbar.connect("value-changed", seekbar_changed)

            hbox = gtk.HBox()
            hbox.add(seekbar)
            label = gtk.Label(str(self.controller.get_sensitivity()) + " %")
            label.set_size_request(30, -1)
            hbox.add(label)

            dialog.vbox.add(hbox)
            dialog.show_all()

            if dialog.run() == gtk.RESPONSE_OK:
                value = seekbar.get_position()
                self.client.set_int(SENSITIVITY, value)
                self.controller.set_sensitivity(value)
                widget.sensitivity = value
                button.set_value(str(self.controller.get_sensitivity()) + " %")

            dialog.destroy()

        def stepLengthButton_value_update():
            if widget.height == 5:
                l_unit = ["m", "ft"]
                stepLengthButton.set_value("Custom value: %.2f %s" % (widget.step_length, l_unit[widget.unit]))
            else:
                h = [ ["< 1.50 m", "1.50 - 1.65 m", "1.66 - 1.80 m", "1.81 - 1.95 m", " > 1.95 m"],
                      ["< 5 ft", "5 - 5.5 ft", "5.5 - 6 ft", "6 - 6.5 ft", "> 6.5 ft"]]
                str = "Using predefined value for height: %s" % h[widget.unit][widget.height]
                stepLengthButton.set_value(str)

        def stepLength_dialog(button):
            def selectorH_changed(selector, data, dialog):
                widget.height = selector.get_active(0)
                widget.client.set_int(HEIGHT, widget.height)
                widget.controller.set_height(widget.height)
                stepLengthButton_value_update()

            def manualButton_clicked(button, dialog):
                dlg = gtk.Dialog()
                dlg.set_title("Custom step length")
                dlg.add_button("OK", gtk.RESPONSE_OK)

                label = gtk.Label("Length")

                entry = hildon.Entry(gtk.HILDON_SIZE_AUTO_WIDTH)
                if widget.height == 5:
                    entry.set_text(str(widget.step_length))

                labelSuffix = gtk.Label()
                if widget.unit == 0:
                    labelSuffix.set_label("m")
                else:
                    labelSuffix.set_label("ft")
                hbox = gtk.HBox()
                hbox.add(label)
                hbox.add(entry)
                hbox.add(labelSuffix)
                dlg.vbox.add(hbox)
                dlg.show_all()

                while 1:
                    response = dlg.run()
                    if response != gtk.RESPONSE_OK:
                        break
                    try:
                        value = float(entry.get_text())
                        if value <= 0:
                            raise ValueError
                        self.controller.set_height(5, value)
                        self.client.set_int(HEIGHT, 5)
                        self.client.set_float(STEP_LENGTH, value)
                        widget.height = 5
                        widget.step_length = value
                        stepLengthButton_value_update()
                        break
                    except ValueError:
                        hildon.hildon_banner_show_information(self, "None", "Invalid length")
                dlg.destroy()
                dialog.destroy()

            def heightButton_clicked(button, dialog):
                dialog.destroy()

            dialog = gtk.Dialog()
            dialog.set_title("Step length")

            manualButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
            manualButton.set_title("Enter custom value")
            manualButton.set_alignment(0, 0.8, 1, 1)
            manualButton.connect("clicked", manualButton_clicked, dialog)

            selectorH = hildon.TouchSelector(text=True)
            selectorH.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
            selectorH.append_text("< 1.50 m")
            selectorH.append_text("1.50 - 1.65 m")
            selectorH.append_text("1.66 - 1.80 m")
            selectorH.append_text("1.81 - 1.95 m")
            selectorH.append_text(" > 1.95 m")

            selectorH_English = hildon.TouchSelector(text=True)
            selectorH_English.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
            selectorH_English.append_text("< 5 ft")
            selectorH_English.append_text("5 - 5.5 ft")
            selectorH_English.append_text("5.5 - 6 ft")
            selectorH_English.append_text("6 - 6.5 ft")
            selectorH_English.append_text("> 6.5 ft")

            heightPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
            heightPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
            heightPicker.set_title("Use predefined values for height")

            if widget.height < 5:
                heightPicker.set_active(widget.height)

            if widget.unit == 0:
                heightPicker.set_selector(selectorH)
            else:
                heightPicker.set_selector(selectorH_English)

            if widget.height < 5:
                heightPicker.set_active(widget.height)
            heightPicker.get_selector().connect("changed", selectorH_changed, dialog)
            heightPicker.connect("value-changed", heightButton_clicked, dialog)

            dialog.vbox.add(heightPicker)
            dialog.vbox.add(manualButton)
            dialog.show_all()

            if  dialog.run() == gtk.RESPONSE_DELETE_EVENT:
                dialog.destroy()

        def donateButton_clicked(button, dialog):
            url = "https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=BKE6E9SLK7NP4&lc=RO&item_name=Pedometer%20Widget&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted"
            command = "dbus-send --system --type=method_call --dest=\"com.nokia.osso_browser\"  --print-reply /com/nokia/osso_browser/request com.nokia.osso_browser.load_url string:\"%s\"" % url
            os.system(command)

        dialog = gtk.Dialog()
        dialog.set_title("Settings")
        dialog.add_button("OK", gtk.RESPONSE_OK)
        self.dialog = dialog

        stepLengthButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        stepLengthButton.set_title("Step length")
        stepLengthButton.set_alignment(0, 0.8, 1, 1)
        stepLengthButton.connect("clicked", stepLength_dialog)
        stepLengthButton_value_update()

        resetButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        resetButton.set_title("Reset total counter")
        resetButton.set_alignment(0, 0.8, 1, 1)
        resetButton.connect("clicked", reset_total_counter)

        alarmButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        alarmButton.set_title("Alarm")
        if self.alarm_controller.get_enable():
            alarmButton.set_value("Enabled")
        else:
            alarmButton.set_value("Disabled")
        alarmButton.set_alignment(0, 0.8, 1, 1)
        alarmButton.connect("clicked", alarmButton_pressed)

        selector = hildon.TouchSelector(text=True)
        selector.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selector.append_text("Walk")
        selector.append_text("Run")
        selector.connect("changed", selector_changed)

        modePicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        modePicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        modePicker.set_title("Mode")
        modePicker.set_selector(selector)
        modePicker.set_active(widget.mode)


        weightButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        weightButton.set_title("Weight")
        weightButton.set_alignment(0, 0.8, 1, 1)
        weightButton.set_value(str(self.controller.get_weight()) + " " + self.controller.get_str_weight_unit() )
        weightButton.connect("clicked", weight_dialog)

        selectorUnit = hildon.TouchSelector(text=True)
        selectorUnit.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorUnit.append_text("Metric (km)")
        selectorUnit.append_text("English (mi)")
        selectorUnit.connect("changed", selectorUnit_changed)

        unitPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        unitPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        unitPicker.set_title("Unit")
        unitPicker.set_selector(selectorUnit)
        unitPicker.set_active(widget.unit)

        selectorUI = hildon.TouchSelector(text=True)
        selectorUI = hildon.TouchSelector(text=True)
        selectorUI.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_SINGLE)
        selectorUI.append_text("Show current + total + graph")
        selectorUI.append_text("Show current + total")
        selectorUI.append_text("Show only current")
        selectorUI.append_text("Show only total")
        selectorUI.connect("changed", selectorUI_changed)

        UIPicker = hildon.PickerButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        UIPicker.set_alignment(0.0, 0.5, 1.0, 1.0)
        UIPicker.set_title("Widget aspect")
        UIPicker.set_selector(selectorUI)
        UIPicker.set_active(widget.aspect)

        sensitivityButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        sensitivityButton.set_title("Sensitivity")
        sensitivityButton.set_alignment(0, 0.8, 1, 1)
        sensitivityButton.set_value(str(self.controller.get_sensitivity()) + " %")
        sensitivityButton.connect("clicked", sensitivity_dialog)

        donateButton = hildon.Button(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT, hildon.BUTTON_ARRANGEMENT_VERTICAL)
        donateButton.set_title("Donate")
        donateButton.set_alignment(0, 0.8, 1, 1)
        donateButton.connect("clicked", donateButton_clicked, dialog)

        logButton = hildon.CheckButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT)
        logButton.set_label("Log data")
        logButton.set_active(widget.logging)
        logButton.connect("toggled", logButton_changed)

        idleButton = hildon.CheckButton(gtk.HILDON_SIZE_AUTO_WIDTH | gtk.HILDON_SIZE_FINGER_HEIGHT)
        idleButton.set_label("Pause time when not walking")
        idleButton.set_active(widget.no_idle_time)
        idleButton.connect("toggled", idleButton_changed)

        pan_area = hildon.PannableArea()
        vbox = gtk.VBox()
        vbox.add(alarmButton)
        vbox.add(modePicker)
        vbox.add(stepLengthButton)
        vbox.add(weightButton)
        vbox.add(unitPicker)
        vbox.add(sensitivityButton)
        vbox.add(UIPicker)
        vbox.add(idleButton)
        vbox.add(resetButton)
        vbox.add(donateButton)
        #vbox.add(logButton)

        pan_area.add_with_viewport(vbox)
        pan_area.set_size_request(-1, 300)

        dialog.vbox.add(pan_area)
        dialog.show_all()

        response = dialog.run()
        dialog.destroy()

    def close_requested(self, widget):
        if self.controller.is_running:
            self.controller.stop_pedometer()
        self.controller.stop_midnight_callback()

    def update_values(self):
        #TODO: do not update if the widget is not on the active desktop
        self.label_second_view.set_label(self.second_view_labels[self.second_view])
        self.update_current()
        self.update_total()

    def button_clicked(self, button):
        if self.controller.is_running:
            self.controller.stop_pedometer()
            self.button.set_icon(ICONSPATH + "play.png")
        else:
            self.controller.start_pedometer()
            self.button.set_icon(ICONSPATH + "stop.png")
            hildon.hildon_banner_show_information(self, "None", "Keep the N900 in a pocket close to your hip for best results")

    def do_expose_event(self, event):
        cr = self.window.cairo_create()
        cr.region(event.window.get_clip_region())
        cr.clip()
        #cr.set_source_rgba(0.4, 0.64, 0.564, 0.5)
        style = self.rc_get_style()
        color = style.lookup_color("DefaultBackgroundColor")
        cr.set_source_rgba (color.red / 65535.0, color.green / 65335.0, color.blue / 65535.0, 0.75);

        radius = 5
        width = self.allocation.width
        height = self.allocation.height

        x = self.allocation.x
        y = self.allocation.y

        cr.move_to(x + radius, y)
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
        cr.set_source_rgba (color.red / 65535.0, color.green / 65335.0, color.blue / 65535.0, 0.5);
        cr.set_line_width(1)
        cr.stroke()

        hildondesktop.HomePluginItem.do_expose_event(self, event)

    def do_realize(self):
        screen = self.get_screen()
        self.set_colormap(screen.get_rgba_colormap())
        self.set_app_paintable(True)
        hildondesktop.HomePluginItem.do_realize(self)

hd_plugin_type = PedometerHomePlugin

import math
import logging

logger = logging.getLogger("pedometer")
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# The code below is just for testing purposes.
# It allows to run the widget as a standalone process.
if __name__ == "__main__":
    import gobject
    gobject.type_register(hd_plugin_type)
    obj = gobject.new(hd_plugin_type, plugin_id="plugin_id")
    obj.show_all()
    gtk.main()
