
class Walk(object):
    def __init__(self, time=0, steps=0, calories=0, dist=0):
        self.time = time
        self.steps = steps
        self.calories = calories
        self.dist = dist
        self.config = Config()

    def __add__(self, other):
        return Walk(self.time + other.time,
                          self.steps + other.steps,
                          self.dist + other.dist,
                          self.calories + other.calories)

    def __sub__(self, other):
        return Walk(self.time - other.time,
                          self.steps - other.steps,
                          self.dist - other.dist,
                          self.calories - other.calories)


    def get_pretty_time(self):
        tdelta = self.time

        hours = int(tdelta / 3600)
        tdelta -= 3600 * hours

        mins = int(tdelta / 60)
        tdelta -= 60 * mins

        return "%.2d:%.2d:%.2d" % (hours, mins, int(tdelta))

    def get_pretty_calories(self):
        return "%.2f" % self.calories

    def get_pretty_distance(self):
        if self.dist > 1000:
            return "%.2f %s" % (self.dist / self.config.unit['conversion'], self.config.unit['suffix'])
        else:
            return "%d %s" % (self.dist * self.config.unit['conversion_small'], self.config.unit['suffix_small'])

    def get_avg_speed(self):
        if self.time == 0:
            return 0
        else:
            return (1.0 * self.dist / self.time) * self.config.unit['conversion_speed']

    def get_pretty_avg_speed(self):
        if self.time == 0:
            return "N/A" + self.config.unit['suffix_speed']
        else:
            return "%.2f %s" % (self.get_avg_speed, self.config.unit['suffix_speed'])

    def get_pretty_calories(self):
        return "%.2f" % self.calories

    def serialize(self):
        return json.dumps({
            'time': self.time,
            'steps': self.steps,
            'calories': self.calories,
            'dist': self.dist
            })

    @staticmethod
    def deserialize(data):
        values = json.loads(data)
        return Walk(*values)
