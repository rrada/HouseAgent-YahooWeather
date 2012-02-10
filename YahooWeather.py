# -*- coding: utf-8 -*-
import urllib
import xml.dom.minidom
import ConfigParser
import os
import pickle
import time
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor, task, defer
from xml.dom.minidom import Node
from houseagent.plugins import pluginapi

CONFIG_FILE="YahooWeather.conf"

class YahooWeather:
    """
    Wrapper class for handle the connection to the coordinator
    """
    def __init__(self):
        callbacks = {"custom": self.cb_custom}
        self.get_configuration()
        self.pluginapi = pluginapi.PluginAPI(self.id, "YahooWeather",
                                             broker_host=self.coordinator_host,
                                             broker_port=self.coordinator_port, **callbacks)

        self.get_locations()

        task.deferLater(reactor, 1.0, self.pluginapi.ready)


    def get_configuration(self):

        #config_file = os.path.join(config_path, "yahooweather", CONFIG_FILE)
        config_file=CONFIG_FILE

        config = ConfigParser.RawConfigParser()
        if os.path.exists(config_file):
            config.read(config_file)
        else:
            config.read('YahooWeather.conf')
        
        self.coordinator_host = config.get("coordinator", "host")
        self.coordinator_port = config.getint("coordinator", "port")
        self.id = config.get("general", "id")
        self.apiURI = config.get("general", "apiURI")
        self.cache_file = config.get("general", "cacheFile")
        self.cache_expire = config.get("general", "cacheExpire")
        self.stamp_file = config.get("general", "stampFile")
        self.units = config.get("general", "units")


    def get_locations(self):
        """
        Get all configured locations
        """
        self.locations = []
        sep = ","
        config = ConfigParser.RawConfigParser()
        config.read(CONFIG_FILE)
        _locations = config.get("locations", "woeids")
        _locations = _locations.split(sep)
        
        for loc in _locations:
            self.locations.append(int(loc))


    def get_weatherdata(self, woeids, units):

        data = {}
        data["units"] = {}
        data["location"] = {}
        unitsKnown = 0
        units_data = {"temperature":"","distance":"", "pressure":"", "speed":""}

        for woeid in woeids:
            try:
                req = self.apiURI+"?w=%s&u=%s" % (woeid, units)
                r = urllib.urlopen(req)
                response = r.read()

                doc = xml.dom.minidom.parseString(response)
                location_data = {"city":"", "country":""}
                wind_data = {"chill":"", "direction":"", "speed":""}
                atmos_data = {"humidity":"", "visibility":"", "pressure":"", "rising":""}
                astro_data = {"sunrise":"", "sunset":""}
                condition_data = {"text":"", "code":"", "temp":"", "date":""}
                forecast_data = {"day":"", "date":"", "low":"", "high":"", "text":"", "code":""}

                if unitsKnown == 0:
                    for node in doc.getElementsByTagName("yweather:units"):
                        for item in units_data.keys():
                            units_data[item] = node.getAttribute(item)
                    unitsKnown = 1
                
                for node in doc.getElementsByTagName("yweather:location"):
                    for item in location_data.keys():
                        location_data[item] = node.getAttribute(item)

                for node in doc.getElementsByTagName("yweather:wind"):
                    for item in wind_data.keys():
                        wind_data[item] = node.getAttribute(item)
                
                for node in doc.getElementsByTagName("yweather:atmosphere"):
                    for item in atmos_data.keys():
                        atmos_data[item] = node.getAttribute(item)
                
                for node in doc.getElementsByTagName("yweather:astronomy"):
                    for item in astro_data.keys():
                        astro_data[item] = node.getAttribute(item)
                
                for node in doc.getElementsByTagName("yweather:condition"):
                    for item in condition_data.keys():
                        condition_data[item] = node.getAttribute(item)
                
                #day = 0
                for node in doc.getElementsByTagName("yweather:forecast"):
                    #for item in forecast_data[day].keys():
                    #for item in forecast_data[1].keys():
                    for item in forecast_data.keys():
                        #forecast_data[day][item] = node.getAttribute(item)
                        forecast_data[item] = node.getAttribute(item)
                    #day = day+1

                result = {"location": location_data,
                            "wind": wind_data,
                            "atmos": atmos_data,
                            "astro": astro_data,
                            "cur_condition": condition_data,
                            "forecast": forecast_data}

                data["location"][woeid] = {}
                data["location"][woeid] = result

            except Exception, e:
                print e
                pass

        data["units"] = units_data
        return data


    def stamp_set(self):
        """
        set stamp to file
        """
        fd = open(self.stamp_file, "w")
        fd.write("%d\n" % time.time())
        os.fsync(fd)
        fd.close()


    def stamp_get(self):
        """
        get stamp
        """
        s = 0 # default = 0 seconds
        if os.path.exists(self.stamp_file):
            fd = open(self.stamp_file, "r")
            s = fd.read()
            fd.close()

        return s


    def stamp_del(self):
        """
        delete stamp
        """
        if os.path.exists(self.stamp_file): 
            os.unlink(self.stamp_file)


    def stamp_check(self):
        """
        check if the stamp is valid or expired, False == Expired; True == Valid
        """
        stamp = float(self.stamp_get())
        if stamp == 0.0:
            return False # not realy expired(it's first time run)

        cur_t = time.time()
        if (cur_t - stamp) > float(self.cache_expire):
            return False # expired
        return True


    def cache_set(self, data):
        """
        write data to shelve cache
        """
        fd = open(self.cache_file, "w")
        pickle.dump(data, fd)
        os.fsync(fd)
        fd.close()
        self.stamp_set()


    def cache_get(self):
        """
        read data from shelve cache
        """
        if os.path.exists(self.cache_file):
            fd = open(self.cache_file, "r")
            data = pickle.load(fd)
            fd.close()

        return data


    def cb_custom(self, action, parameters):
        """
        This function is a callback handler for custom commands
        received from the coordinator.
        @param action: the custom action to handle
        @param parameters: the parameters passed with the custom action
        """
        if action == "get_forecast":
            if self.stamp_check() is False:
                data = self.get_weatherdata(self.locations, self.units)
                self.cache_set(data)
            else:
                data = self.cache_get()

            d = defer.Deferred()
            d.callback(data)
            return d

        # WOEID/Location management
        elif action == "get_woeids":
            d = defer.Deferred()
            d.callback(self.locations)
            return d

        elif action == "add_woeid":
            _woeids = self.locations
            _woeids.append(parameters["woeid"])
            woeids = ",".join(str(v) for v in _woeids)

            config = ConfigParser.RawConfigParser()
            config.read(CONFIG_FILE)
            config.set("locations", "woeids", woeids)
            
            with open(CONFIG_FILE, "wb") as configfile:
                config.write(configfile)
                
            # reload locations
            self.get_locations()

            # remove stamp - force download of new data
            self.stamp_del()
            
            d = defer.Deferred()
            d.callback('OK')
            return d
        
        elif action == "del_woeid":
            _woeids = self.locations
            _del_woeid = int(parameters["woeid"])
            _woeids.remove(_del_woeid)
            woeids = ",".join(str(v) for v in _woeids)

            config = ConfigParser.RawConfigParser()
            config.read(CONFIG_FILE)
            config.set("locations", "woeids", woeids)
            
            with open(CONFIG_FILE, "wb") as configfile:
                config.write(configfile)
                
            # reload locations
            self.get_locations()

            # remove stamp - force download of new data
            self.stamp_del()
            
            d = defer.Deferred()
            d.callback("OK")
            return d


if __name__ == '__main__':
    YahooWeather()
    reactor.run()
